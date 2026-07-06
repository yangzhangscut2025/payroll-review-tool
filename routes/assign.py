from flask import Blueprint, request, redirect, url_for, session, jsonify
from models import db, Project, ModuleAssignment

assign_bp = Blueprint('assign', __name__)


@assign_bp.route('/projects/<int:project_id>/assign', methods=['POST'])
def assign_module(project_id):
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登录'}), 401

    project = Project.query.get_or_404(project_id)
    if project.created_by != username:
        return jsonify({'error': '仅项目负责人可分配模块'}), 403

    data = request.get_json()
    module_l1 = data.get('module_l1', '').strip()
    assignee = data.get('assignee', '').strip()

    if not module_l1:
        return jsonify({'error': '请指定模块'}), 400

    if not assignee:
        # Un-assign
        ModuleAssignment.query.filter_by(project_id=project.id,
                                         module_l1=module_l1).delete()
        db.session.commit()
        return jsonify({'ok': True})

    existing = ModuleAssignment.query.filter_by(project_id=project.id,
                                                module_l1=module_l1).first()
    if existing:
        existing.assignee = assignee
    else:
        ma = ModuleAssignment(project_id=project.id, module_l1=module_l1,
                              assignee=assignee, status='进行中')
        db.session.add(ma)

    db.session.commit()
    return jsonify({'ok': True})


@assign_bp.route('/api/projects/<int:project_id>/assignments')
def get_assignments(project_id):
    """Get current assignments for a project."""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登录'}), 401

    assignments = ModuleAssignment.query.filter_by(project_id=project_id).all()
    return jsonify([
        {'module_l1': a.module_l1, 'assignee': a.assignee, 'status': a.status}
        for a in assignments
    ])
