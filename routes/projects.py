from flask import Blueprint, render_template, request, redirect, url_for, session
from models import db, Project, ModuleAssignment, ReviewField
from users import get_all_users
from datetime import datetime, timezone

projects_bp = Blueprint('projects', __name__)


def login_required():
    """Check if user is logged in. Returns username or None."""
    return session.get('username')


@projects_bp.route('/projects')
def project_list():
    username = login_required()
    if not username:
        return redirect(url_for('auth.login_page'))

    country_filter = request.args.get('country', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Project.query.filter(Project.deleted_at.is_(None))
    if country_filter:
        query = query.filter(Project.country.like(f'%{country_filter}%'))
    if status_filter in ('进行中', '已完成'):
        query = query.filter(Project.status == status_filter)

    projects = query.order_by(Project.country.asc(), Project.created_at.desc()).all()

    return render_template('index.html', projects=projects, username=username,
                           country_filter=country_filter, status_filter=status_filter)


@projects_bp.route('/projects/create', methods=['POST'])
def create_project():
    username = login_required()
    if not username:
        return redirect(url_for('auth.login_page'))

    name = request.form.get('name', '').strip()
    country = request.form.get('country', '').strip()

    if not name or not country:
        return render_template('index.html', error='文件名称和国家为必填项',
                               projects=[], username=username)

    project = Project(name=name, country=country, created_by=username)
    db.session.add(project)
    db.session.commit()

    return redirect(url_for('projects.project_detail', project_id=project.id))


@projects_bp.route('/projects/<int:project_id>')
def project_detail(project_id):
    username = login_required()
    if not username:
        return redirect(url_for('auth.login_page'))

    project = Project.query.get_or_404(project_id)

    # Get module assignments
    assignments = ModuleAssignment.query.filter_by(project_id=project.id).all()
    assigned_map = {a.module_l1: a for a in assignments}

    # Calculate module-level progress
    l1_modules = {}
    fields = ReviewField.query.filter_by(project_id=project.id).all()
    for f in fields:
        if f.module_l1 not in l1_modules:
            l1_modules[f.module_l1] = {'total': 0, 'completed': 0}
        l1_modules[f.module_l1]['total'] += 1
        if f.status != '待审阅':
            l1_modules[f.module_l1]['completed'] += 1

    return render_template('project_detail.html', project=project,
                           username=username, l1_modules=l1_modules,
                           assigned_map=assigned_map,
                           user_list=get_all_users())


@projects_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    username = login_required()
    if not username:
        return redirect(url_for('auth.login_page'))

    project = Project.query.get_or_404(project_id)
    if project.created_by != username:
        return "无权限", 403

    # Physical delete
    ReviewField.query.filter_by(project_id=project.id).delete()
    ModuleAssignment.query.filter_by(project_id=project.id).delete()
    db.session.delete(project)
    db.session.commit()

    return redirect(url_for('projects.project_list'))
