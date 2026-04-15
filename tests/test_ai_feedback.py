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


from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

class TestAIFeedbackService(unittest.IsolatedAsyncioTestCase):
    async def test_generate_done_on_success(self):
        from app.services.ai_feedback_service import AIFeedbackService
        submission = SimpleNamespace(id="sub-1", image_paths=["media/t.jpg"], ai_feedback=None)
        svc = AIFeedbackService(AsyncMock())
        with patch.object(svc, '_recognize_char', new=AsyncMock(return_value="永")), \
             patch.object(svc, '_call_vision_model', new=AsyncMock(return_value={
                 "stroke_score": 7, "structure_score": 8, "overall_score": 6, "summary": "不错"
             })), \
             patch.object(svc.repo, 'get', new=AsyncMock(return_value=submission)), \
             patch.object(svc.repo, 'update', new=AsyncMock(return_value=submission)):
            await svc.generate("sub-1")
            kwargs = svc.repo.update.call_args[0][1]
            self.assertEqual(kwargs['ai_feedback']['status'], 'done')
            self.assertEqual(len(kwargs['ai_feedback']['items']), 1)

    async def test_generate_failed_on_exception(self):
        from app.services.ai_feedback_service import AIFeedbackService
        submission = SimpleNamespace(id="sub-1", image_paths=["media/t.jpg"], ai_feedback=None)
        svc = AIFeedbackService(AsyncMock())
        with patch.object(svc, '_recognize_char', new=AsyncMock(side_effect=Exception("ocr error"))), \
             patch.object(svc.repo, 'get', new=AsyncMock(return_value=submission)), \
             patch.object(svc.repo, 'update', new=AsyncMock(return_value=submission)):
            await svc.generate("sub-1")
            kwargs = svc.repo.update.call_args[0][1]
            self.assertEqual(kwargs['ai_feedback']['status'], 'failed')
