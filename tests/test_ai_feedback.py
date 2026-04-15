from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from app.models.submission import Submission
import os
import unittest
from datetime import datetime
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DB", "charwork")


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
            self.assertIn('generated_at', kwargs['ai_feedback'])

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
            self.assertIn('generated_at', kwargs['ai_feedback'])


class TestAIFeedbackTask(unittest.TestCase):
    def test_task_is_registered(self):
        from app.tasks.ai_feedback_tasks import generate_ai_feedback
        # 验证 task 已注册到 celery，name 与约定一致
        self.assertEqual(generate_ai_feedback.name, "generate_ai_feedback")

    def test_generate_calls_service(self):
        from app.tasks.ai_feedback_tasks import _generate
        with patch('app.tasks.ai_feedback_tasks.AsyncSessionLocal') as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch('app.services.ai_feedback_service.AIFeedbackService') as mock_svc_cls:
                mock_svc = AsyncMock()
                mock_svc.generate = AsyncMock()
                mock_svc_cls.return_value = mock_svc
                import asyncio
                result = asyncio.run(_generate("sub-1"))
                self.assertEqual(result['status'], 'ok')


class TestSubmissionServiceUpdates(unittest.IsolatedAsyncioTestCase):
    async def test_grade_writes_teacher_feedback(self):
        from app.services.submission_service import SubmissionService
        from app.schemas.submission import SubmissionGrade
        from unittest.mock import MagicMock

        submission = SimpleNamespace(
            id="sub-1", assignment_id="asg-1", student_id="stu-1",
            management_system_id="ms-1", status="submitted",
            score=None, teacher_feedback=None, ai_feedback=None,
            submitted_at=datetime(2026, 4, 15), graded_at=None,
            content=None, image_paths=None,
        )
        svc = SubmissionService(AsyncMock())
        svc.repo.get = AsyncMock(return_value=submission)
        svc.repo.update = AsyncMock(return_value=submission)
        svc.repo.db = AsyncMock()
        svc.repo.db.execute = AsyncMock(
            return_value=AsyncMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )
        svc.repo.commit = AsyncMock()

        with patch('app.services.submission_service.send_grade_notification') as mock_task:
            mock_task.delay = MagicMock()
            await svc.grade_submission(
                "sub-1", SubmissionGrade(score=9, feedback="很好"), "ms-1", "teacher-1"
            )

        update_data = svc.repo.update.call_args[0][1]
        self.assertIn('teacher_feedback', update_data)
        self.assertEqual(update_data['teacher_feedback'], "很好")

    async def test_get_ai_feedback_returns_field(self):
        from app.services.submission_service import SubmissionService

        submission = SimpleNamespace(
            id="sub-1", assignment_id="asg-1", student_id="stu-1",
            management_system_id="ms-1", status="submitted",
            score=None, teacher_feedback=None,
            ai_feedback={"status": "done", "generated_at": "2026-04-15T10:00:00", "items": []},
            submitted_at=datetime(2026, 4, 15), graded_at=None,
            content=None, image_paths=None,
        )
        svc = SubmissionService(AsyncMock())
        svc.repo.get = AsyncMock(return_value=submission)

        result = await svc.get_ai_feedback("sub-1", "ms-1")
        self.assertEqual(result['status'], 'done')
