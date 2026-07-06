from flask import Blueprint, render_template, request, redirect, url_for, session
from users import get_all_users

auth_bp = Blueprint('auth', __name__)


def validate_login(name):
    """Check if name matches any user (English or Chinese name). Returns the English name."""
    if not name:
        return None
    users = get_all_users()
    for u in users:
        if name.lower() == u['english'].lower() or name == u['chinese']:
            return u['english']
    return None


@auth_bp.route('/', methods=['GET'])
def login_page():
    if 'username' in session:
        return redirect(url_for('projects.project_list'))
    users = get_all_users()
    return render_template('login.html', users=users)


@auth_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    valid = validate_login(username)
    if not valid:
        users = get_all_users()
        return render_template('login.html', error=f'用户"{username}"不存在，请使用注册用户名登录',
                               users=users)
    session['username'] = valid
    return redirect(url_for('projects.project_list'))


@auth_bp.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('auth.login_page'))
