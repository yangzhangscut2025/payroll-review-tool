import os
from datetime import datetime
from flask import Blueprint, request, session, send_file, redirect, url_for, current_app
from models import db, Project, ReviewField
from excel_writer import generate_review_excel

export_bp = Blueprint('export', __name__)


@export_bp.route('/projects/<int:project_id>/export')
def export_result(project_id):
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login_page'))

    project = Project.query.get_or_404(project_id)
    if not project.file_path:
        return "请先上传Excel文件", 400

    fields = ReviewField.query.filter_by(project_id=project.id).all()
    if not fields:
        return "请先进行审阅", 400

    safe_name = project.name.replace('/', '_').replace('\\', '_')
    date_str = datetime.now().strftime('%Y%m%d')
    output_name = f"{safe_name}_审阅结果_{date_str}.xlsx"
    output_path = os.path.join(os.path.dirname(project.file_path), output_name)

    review_map = {}
    html_count = 0
    for f in fields:
        review_map[(f.row_index, f.field_type)] = f
        if f.changed_content and '<span style' in f.changed_content:
            html_count += 1

    current_app.logger.info(f"Export: {len(fields)} fields, {html_count} with color spans")

    generate_review_excel(project.file_path, output_path, review_map, project.format_version or 'v1')

    project.output_path = output_path
    project.updated_at = db.func.now()
    db.session.commit()

    return send_file(output_path, as_attachment=True, download_name=output_name)
