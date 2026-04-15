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
        self.assertTrue(hasattr(Submission(), 'ai_feedback'))

    def test_has_teacher_feedback_field(self):
        self.assertTrue(hasattr(Submission(), 'teacher_feedback'))

    def test_no_feedback_field(self):
        self.assertFalse(hasattr(Submission(), 'feedback'))
