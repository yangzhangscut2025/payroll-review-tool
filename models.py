from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json

db = SQLAlchemy()


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    file_path = db.Column(db.String(500))
    output_path = db.Column(db.String(500))
    total_modules = db.Column(db.Integer, default=0)
    completed_modules = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='进行中')
    deleted_at = db.Column(db.DateTime, nullable=True)

    assignments = db.relationship('ModuleAssignment', backref='project',
                                  lazy='dynamic', cascade='all, delete-orphan')
    review_fields = db.relationship('ReviewField', backref='project',
                                    lazy='dynamic', cascade='all, delete-orphan')


class ModuleAssignment(db.Model):
    __tablename__ = 'module_assignments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    module_l1 = db.Column(db.String(200), nullable=False)
    assignee = db.Column(db.String(100), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='待开始')

    __table_args__ = (
        db.UniqueConstraint('project_id', 'module_l1', name='uq_project_l1'),
    )


class ReviewField(db.Model):
    __tablename__ = 'review_fields'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    row_index = db.Column(db.Integer, nullable=False)
    module_l1 = db.Column(db.String(200), nullable=False)
    module_l2 = db.Column(db.String(200), nullable=False)
    field_type = db.Column(db.String(50), nullable=False)
    original_content = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='待审阅')
    change_type = db.Column(db.String(20))
    internal_note = db.Column(db.Text, default='')
    changed_content = db.Column(db.Text, default='')
    reviewer = db.Column(db.String(100))
    reviewed_at = db.Column(db.DateTime)
    link_urls = db.Column(db.Text, default='[]')
    link_statuses = db.Column(db.Text, default='{}')
    corrected_links = db.Column(db.Text, default='{}')

    def get_link_urls(self):
        return json.loads(self.link_urls) if self.link_urls else []

    def set_link_urls(self, urls):
        self.link_urls = json.dumps(urls, ensure_ascii=False)

    def get_link_statuses(self):
        return json.loads(self.link_statuses) if self.link_statuses else {}

    def set_link_statuses(self, statuses):
        self.link_statuses = json.dumps(statuses, ensure_ascii=False)

    def get_corrected_links(self):
        return json.loads(self.corrected_links) if self.corrected_links else {}

    def set_corrected_links(self, links):
        self.corrected_links = json.dumps(links, ensure_ascii=False)
