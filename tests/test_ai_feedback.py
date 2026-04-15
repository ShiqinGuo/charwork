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


class TestSubmissionSchemas(unittest.TestCase):
    def test_response_has_teacher_feedback(self):
        from app.schemas.submission import SubmissionResponse
        self.assertIn('teacher_feedback', SubmissionResponse.model_fields)

    def test_response_has_ai_feedback(self):
        from app.schemas.submission import SubmissionResponse
        self.assertIn('ai_feedback', SubmissionResponse.model_fields)

    def test_teacher_feedback_update_schema(self):
        from app.schemas.submission import TeacherFeedbackUpdate
        obj = TeacherFeedbackUpdate(teacher_feedback="写得不错", score=8)
        self.assertEqual(obj.score, 8)
