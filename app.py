from flask import Flask
from config import Config
from models import db
import logging
from logging.handlers import RotatingFileHandler
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 日志配置
    log_file = os.path.join(os.path.dirname(__file__), 'app.log')
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=3)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from routes.auth import auth_bp
    from routes.projects import projects_bp
    from routes.upload import upload_bp
    from routes.assign import assign_bp
    from routes.review import review_bp
    from routes.export import export_bp
    from routes.ai_usage import ai_usage_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(assign_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(ai_usage_bp)

    # 请求日志
    @app.before_request
    def log_request():
        from flask import request
        app.logger.info(f'{request.method} {request.path}')

    return app


if __name__ == '__main__':
    app = create_app()
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000, threads=16)
    print('Waitress server running on http://0.0.0.0:5000')
