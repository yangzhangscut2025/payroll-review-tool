"""溯源页面：在当前l2模块的离线MD中搜索证据。"""
import os
from flask import Blueprint, render_template, request, session, redirect, url_for
from models import db, Project, ReviewField
from keyword_checker import trace_one_field

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

    # 定位 MD 文件夹：和上传的 Excel 同目录同名
    base_name = os.path.splitext(os.path.basename(project.file_path))[0]
    md_dir = os.path.join(os.path.dirname(project.file_path), base_name)
    if not os.path.isdir(md_dir):
        md_dir = ''

    # 构建 l2 列表
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

    # 收集当前 l2 的所有实务内容字段并溯源
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

    return render_template('trace.html',
                           project=project,
                           username=username,
                           l2_list=l2_list,
                           l2_index=l2_index,
                           current=current,
                           trace_results=trace_results,
                           md_dir_exists=bool(md_dir))
