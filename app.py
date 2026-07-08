from flask import Flask
from config import Config
from models import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from routes.auth import auth_bp
    from routes.projects import projects_bp
    from routes.upload import upload_bp
    from routes.assign import assign_bp
    from routes.review import review_bp
    from routes.export import export_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(assign_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(export_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
