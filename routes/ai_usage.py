from flask import Blueprint, render_template, session, redirect, url_for
from models import db, AIUsageLog
from sqlalchemy import func

ai_usage_bp = Blueprint('ai_usage', __name__)

# DeepSeek pricing (RMB per 1M tokens)
PRICE_INPUT = 1.0   # ¥1/1M input tokens
PRICE_OUTPUT = 2.0  # ¥2/1M output tokens


@ai_usage_bp.route('/ai-usage')
def usage_dashboard():
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login_page'))

    # Summary stats
    total_calls = db.session.query(func.count(AIUsageLog.id)).scalar() or 0
    total_prompt = db.session.query(func.sum(AIUsageLog.prompt_tokens)).scalar() or 0
    total_completion = db.session.query(func.sum(AIUsageLog.completion_tokens)).scalar() or 0
    total_tokens = total_prompt + total_completion
    est_cost = (total_prompt / 1_000_000) * PRICE_INPUT + (total_completion / 1_000_000) * PRICE_OUTPUT

    # Per-user stats
    user_rows = db.session.query(
        AIUsageLog.username,
        func.count(AIUsageLog.id).label('calls'),
        func.sum(AIUsageLog.prompt_tokens).label('prompt_tok'),
        func.sum(AIUsageLog.completion_tokens).label('completion_tok'),
    ).group_by(AIUsageLog.username).order_by(func.sum(AIUsageLog.prompt_tokens + AIUsageLog.completion_tokens).desc()).all()

    user_stats = []
    for row in user_rows:
        pt = row.prompt_tok or 0
        ct = row.completion_tok or 0
        user_stats.append({
            'username': row.username,
            'calls': row.calls,
            'prompt_tokens': pt,
            'completion_tokens': ct,
            'total_tokens': pt + ct,
            'est_cost': (pt / 1_000_000) * PRICE_INPUT + (ct / 1_000_000) * PRICE_OUTPUT,
        })

    # Per-project stats
    project_rows = db.session.query(
        AIUsageLog.project_name,
        AIUsageLog.project_id,
        func.count(AIUsageLog.id).label('calls'),
        func.sum(AIUsageLog.prompt_tokens).label('prompt_tok'),
        func.sum(AIUsageLog.completion_tokens).label('completion_tok'),
    ).group_by(AIUsageLog.project_id, AIUsageLog.project_name).order_by(func.sum(AIUsageLog.prompt_tokens + AIUsageLog.completion_tokens).desc()).all()

    project_stats = []
    for row in project_rows:
        pt = row.prompt_tok or 0
        ct = row.completion_tok or 0
        project_stats.append({
            'project_id': row.project_id,
            'project_name': row.project_name,
            'calls': row.calls,
            'prompt_tokens': pt,
            'completion_tokens': ct,
            'total_tokens': pt + ct,
            'est_cost': (pt / 1_000_000) * PRICE_INPUT + (ct / 1_000_000) * PRICE_OUTPUT,
        })

    # Recent calls (last 50)
    recent_logs = AIUsageLog.query.order_by(AIUsageLog.created_at.desc()).limit(50).all()

    return render_template('ai_usage.html',
                           username=username,
                           total_calls=total_calls,
                           total_tokens=total_tokens,
                           total_prompt=total_prompt,
                           total_completion=total_completion,
                           est_cost=est_cost,
                           user_stats=user_stats,
                           project_stats=project_stats,
                           recent_logs=recent_logs)