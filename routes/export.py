import os
import json
import uuid
import threading
from datetime import datetime
from flask import Blueprint, request, session, send_file, redirect, url_for, current_app, jsonify
from models import db, Project, ReviewField
from excel_writer import generate_review_excel, LANG_MAP

export_bp = Blueprint('export', __name__)

# In-memory progress store (cleared on restart)
_export_progress = {}

TASK_TTL = 3600  # auto-clean tasks older than 1 hour


def _cleanup_tasks():
    """Remove expired tasks from progress store."""
    import time
    now = time.time()
    expired = [tid for tid, info in _export_progress.items()
               if info.get('_created', 0) < now - TASK_TTL]
    for tid in expired:
        _export_progress.pop(tid, None)


def _find_active_task(project_id):
    """Check if there's already an active export for this project."""
    for tid, info in _export_progress.items():
        if info.get('project_id') == project_id and info['status'] == 'processing':
            return tid
    return None


@export_bp.route('/api/projects/<int:project_id>/export-preview', methods=['POST'])
def export_preview(project_id):
    """Return export preview: sheets, fields, translation estimates."""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登录'}), 401

    project = Project.query.get_or_404(project_id)
    if not project.file_path:
        return jsonify({'error': '请先上传Excel文件'}), 400

    fields = ReviewField.query.filter_by(project_id=project.id).all()
    if not fields:
        return jsonify({'error': '请先进行审阅'}), 400

    review_map = {}
    for f in fields:
        review_map[(f.row_index, f.field_type)] = f

    # Check which sheets exist
    import openpyxl
    wb = openpyxl.load_workbook(project.file_path, data_only=True)
    sheets = []
    for name in wb.sheetnames:
        if name == 'zh_Chinese' or name in LANG_MAP:
            sheets.append({
                'name': name,
                'label': '中文' if name == 'zh_Chinese' else LANG_MAP.get(name, name),
                'translate': name in LANG_MAP,
            })
    wb.close()

    # Count translatable items
    translate_items = sum(1 for rf in review_map.values()
                          if rf.changed_content and rf.changed_content.strip())

    # Estimate tokens and cost
    est_chars = sum(len(rf.changed_content) for rf in review_map.values()
                    if rf.changed_content)
    est_tokens = int(est_chars * 1.5)  # rough: 1.5 tokens per Chinese char
    translate_sheets = sum(1 for s in sheets if s['translate'])
    total_tokens = est_tokens * translate_sheets
    est_cost = (total_tokens / 1_000_000) * 1.0  # input ¥1/M tokens
    est_time = max(5, translate_items * translate_sheets * 0.3)  # ~0.3s per item

    return jsonify({
        'ok': True,
        'sheets': sheets,
        'total_fields': len(fields),
        'translate_items': translate_items,
        'est_tokens': total_tokens,
        'est_cost': round(est_cost, 4),
        'est_time_seconds': round(est_time, 1),
    })


@export_bp.route('/api/projects/<int:project_id>/export-start', methods=['POST'])
def export_start(project_id):
    """Start async export, return task_id for progress polling."""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登录'}), 401

    project = Project.query.get_or_404(project_id)
    if not project.file_path:
        return jsonify({'error': '请先上传Excel文件'}), 400

    fields = ReviewField.query.filter_by(project_id=project.id).all()
    if not fields:
        return jsonify({'error': '请先进行审阅'}), 400

    review_map = {}
    for f in fields:
        review_map[(f.row_index, f.field_type)] = f

    safe_name = project.name.replace('/', '_').replace('\\', '_')
    date_str = datetime.now().strftime('%Y%m%d')
    output_name = f"{safe_name}_审阅结果_{date_str}.xlsx"
    output_path = os.path.join(os.path.dirname(project.file_path), output_name)

    task_id = uuid.uuid4().hex[:12]

    # Check for existing active export
    existing = _find_active_task(project_id)
    if existing:
        return jsonify({'ok': True, 'task_id': existing, 'resumed': True})

    _cleanup_tasks()
    _export_progress[task_id] = {
        'status': 'processing',
        'percentage': 0,
        'sheet': '',
        'detail': '准备中...',
        'output_path': output_path,
        'output_name': output_name,
        'error': None,
        'project_id': project_id,
        '_created': __import__('time').time(),
    }

    def progress_callback(pct, sheet, detail):
        if task_id in _export_progress:
            _export_progress[task_id].update({
                'percentage': pct,
                'sheet': sheet,
                'detail': detail,
            })

    app = current_app._get_current_object()

    def run_export():
        try:
            warnings, usage = generate_review_excel(
                project.file_path, output_path, review_map,
                project.format_version or 'v1',
                progress_callback=progress_callback,
            )
            _export_progress[task_id]['status'] = 'done'
            _export_progress[task_id]['percentage'] = 100
            detail = '导出完成'
            if warnings:
                detail += ' (⚠️ ' + '; '.join(warnings) + ')'
            _export_progress[task_id]['detail'] = detail
            with app.app_context():
                from models import db, Project, AIUsageLog
                p = db.session.get(Project, project_id)
                if p:
                    p.output_path = output_path
                    p.updated_at = db.func.now()
                # Log translation usage
                if usage['prompt_tokens'] > 0 or usage['completion_tokens'] > 0:
                    log = AIUsageLog(
                        username=username,
                        project_id=project_id,
                        project_name=project.name,
                        module_l1='export',
                        module_l2='translation',
                        model=current_app.config.get('DEEPSEEK_MODEL', 'deepseek-chat'),
                        prompt_tokens=usage['prompt_tokens'],
                        completion_tokens=usage['completion_tokens'],
                    )
                    db.session.add(log)
                db.session.commit()
        except Exception as e:
            _export_progress[task_id]['status'] = 'error'
            _export_progress[task_id]['error'] = str(e)
            _export_progress[task_id]['detail'] = '导出失败'

    thread = threading.Thread(target=run_export, daemon=True)
    thread.start()

    return jsonify({'ok': True, 'task_id': task_id})


@export_bp.route('/api/projects/<int:project_id>/export-progress/<task_id>')
def export_progress(project_id, task_id):
    """Poll for export progress."""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登录'}), 401

    info = _export_progress.get(task_id)
    if not info:
        return jsonify({'error': '任务不存在或已过期'}), 404

    _cleanup_tasks()

    return jsonify({
        'status': info['status'],
        'percentage': info['percentage'],
        'sheet': info['sheet'],
        'detail': info['detail'],
        'error': info.get('error'),
    })


@export_bp.route('/api/projects/<int:project_id>/export-download/<task_id>')
def export_download(project_id, task_id):
    """Download the exported file."""
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login_page'))

    info = _export_progress.get(task_id)
    if not info or info['status'] != 'done':
        return "导出尚未完成或已过期", 404

    output_path = info['output_path']
    output_name = info['output_name']

    # Clean up progress
    _export_progress.pop(task_id, None)

    return send_file(output_path, as_attachment=True, download_name=output_name)


@export_bp.route('/projects/<int:project_id>/export')
def export_result(project_id):
    """Legacy: redirect to project detail page (new flow uses async export)."""
    return redirect(url_for('projects.project_detail', project_id=project_id))