"""溯源页面：向量检索 + 关键词匹配双模式。"""
import os
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from models import db, Project, ReviewField
from keyword_checker import trace_one_field
from vector_search import search_similar, build_index, index_exists

trace_bp = Blueprint('trace', __name__)

TRACE_MAP = {
    '实务内容（官方）': '参考依据（官方）',
    '实务内容（行业通用）': '参考依据（行业权威）',
    '实务内容（内部口径）': '参考依据（行业常规）',
}


@trace_bp.route('/projects/<int:project_id>/trace')
def trace_page(project_id):
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login_page'))

    project = Project.query.get_or_404(project_id)
    if not project.file_path:
        return "请先上传Excel", 400

    base_name = os.path.splitext(os.path.basename(project.file_path))[0]
    md_dir = os.path.join(os.path.dirname(project.file_path), base_name)
    if not os.path.isdir(md_dir):
        md_dir = ''

    fields = ReviewField.query.filter_by(project_id=project.id)\
        .order_by(ReviewField.row_index).all()
    l2_list = []
    seen = set()
    for f in fields:
        key = (f.module_l1, f.module_l2)
        if key not in seen:
            seen.add(key)
            l2_list.append({'l1': f.module_l1, 'l2': f.module_l2})

    l2_index = request.args.get('l2', 0, type=int)
    if l2_index < 0 or l2_index >= len(l2_list):
        l2_index = 0
    current = l2_list[l2_index]

    # 关键词匹配（兜底）
    trace_results = []
    if md_dir:
        l2_fields = [f for f in fields
                     if f.module_l1 == current['l1'] and f.module_l2 == current['l2']]
        for field in l2_fields:
            ref_type = TRACE_MAP.get(field.field_type)
            if not ref_type or not (field.original_content or '').strip():
                continue
            sent_results = trace_one_field(field.original_content, md_dir)
            trace_results.append({
                'field_id': field.id,
                'field_type': field.field_type,
                'ref_type': ref_type,
                'sentences': sent_results,
            })

    # MD 文件列表
    md_files = {}
    if md_dir:
        for ref_type in set(TRACE_MAP.values()):
            files = [f for f in os.listdir(md_dir) if f.endswith('.md') and ref_type in f]
            if files:
                md_files[ref_type] = sorted(files)[:20]

    return render_template('trace.html',
                           project=project,
                           username=username,
                           l2_list=l2_list,
                           l2_index=l2_index,
                           current=current,
                           trace_results=trace_results,
                           md_files=md_files,
                           md_dir=md_dir,
                           md_dir_exists=bool(md_dir),
                           index_ready=index_exists(project_id))


@trace_bp.route('/api/projects/<int:project_id>/build-index')
def build_index_api(project_id):
    """构建向量索引。"""
    project = Project.query.get_or_404(project_id)
    if not project.file_path:
        return jsonify({'error': '请先上传Excel'}), 400
    base_name = os.path.splitext(os.path.basename(project.file_path))[0]
    md_dir = os.path.join(os.path.dirname(project.file_path), base_name)
    if not os.path.isdir(md_dir):
        return jsonify({'error': 'MD 目录不存在'}), 404

    try:
        count = build_index(md_dir, project_id)
        return jsonify({'ok': True, 'blocks': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trace_bp.route('/api/vector-search')
def vector_search():
    """向量检索。"""
    project_id = request.args.get('project_id', type=int)
    query = request.args.get('q', '')
    top_k = request.args.get('top_k', 5, type=int)
    if not project_id or not query.strip():
        return jsonify({'results': []})

    results = search_similar(project_id, query, top_k)
    return jsonify({'results': results})


@trace_bp.route('/api/md-content')
def md_content():
    import urllib.parse
    path = request.args.get('path', '')
    path = urllib.parse.unquote(path)
    if not os.path.exists(path) or '..' in path:
        return jsonify({'error': '文件不存在'}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content, 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500