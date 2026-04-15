import os, unittest
from datetime import datetime
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DB", "charwork")

from app.models.submission import Submission

class TestSubmissionModel(unittest.TestCase):
    def test_has_ai_feedback_field(self):
        col_names = {c.name for c in Submission.__table__.columns}
        self.assertIn('ai_feedback', col_names)

    def test_has_teacher_feedback_field(self):
        col_names = {c.name for c in Submission.__table__.columns}
        self.assertIn('teacher_feedback', col_names)

    def test_no_feedback_field(self):
        col_names = {c.name for c in Submission.__table__.columns}
        self.assertNotIn('feedback', col_names)
