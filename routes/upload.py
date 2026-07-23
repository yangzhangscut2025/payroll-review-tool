import os
from flask import Blueprint, request, redirect, url_for, session, flash
from models import db, Project, ReviewField
from excel_parser import parse_excel
from config import Config

upload_bp = Blueprint('upload', __name__)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@upload_bp.route('/projects/<int:project_id>/upload', methods=['POST'])
def upload_excel(project_id):
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login_page'))

    project = Project.query.get_or_404(project_id)

    if project.created_by != username:
        return "仅项目负责人可上传文件", 403

    if 'file' not in request.files:
        return "未选择文件", 400

    file = request.files['file']
    if file.filename == '':
        return "未选择文件", 400

    if not allowed_file(file.filename):
        return "仅支持 .xlsx 和 .xlsm 格式", 400

    # Save file
    ext = file.filename.rsplit('.', 1)[1].lower()
    ts = __import__('time').strftime('%Y%m%d_%H%M%S')
    save_name = f"project_{project.id}_{ts}.{ext}"
    filepath = os.path.join(Config.UPLOAD_FOLDER, save_name)
    file.save(filepath)
    project.file_path = filepath
    db.session.commit()

    # Parse and initialize review fields
    try:
        # Clean old review data before re-parsing
        ReviewField.query.filter_by(project_id=project.id).delete()
        result = parse_excel(filepath, project.id, db)
        project.total_modules = result['l1_count']
        project.completed_modules = 0
        project.format_version = result.get('format_version', 'v1')
        project.status = '进行中'
        db.session.commit()
    except ValueError as e:
        # Clean up on parse error
        if os.path.exists(filepath):
            os.remove(filepath)
        project.file_path = None
        db.session.commit()
        flash(str(e), 'error')
        return redirect(url_for('projects.project_detail', project_id=project.id))

    flash(f"上传成功！共 {result['l1_count']} 个模块, {result['l2_count']} 个子模块, "
          f"{result['total_fields']} 个审阅字段")
    return redirect(url_for('projects.project_detail', project_id=project.id))
