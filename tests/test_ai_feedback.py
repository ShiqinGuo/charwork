import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DB", "charwork")

from app.models.ai_feedback import AIFeedback
from app.models.submission import Submission


class TestSubmissionModel(unittest.TestCase):
    def test_has_ai_feedback_field(self):
        col_names = {c.name for c in Submission.__table__.columns}
        self.assertIn("ai_feedback", col_names)

    def test_has_teacher_feedback_field(self):
        col_names = {c.name for c in Submission.__table__.columns}
        self.assertIn("teacher_feedback", col_names)

    def test_no_feedback_field(self):
        col_names = {c.name for c in Submission.__table__.columns}
        self.assertNotIn("feedback", col_names)


class TestAIFeedbackModel(unittest.TestCase):
    def test_has_feedback_core_columns(self):
        col_names = {c.name for c in AIFeedback.__table__.columns}
        self.assertIn("target_type", col_names)
        self.assertIn("feedback_scope", col_names)
        self.assertIn("visibility_scope", col_names)
        self.assertIn("result_payload", col_names)


class TestSubmissionSchemas(unittest.TestCase):
    def test_response_has_teacher_feedback(self):
        from app.schemas.submission import SubmissionResponse

        self.assertIn("teacher_feedback", SubmissionResponse.model_fields)

    def test_response_no_longer_has_ai_feedback(self):
        from app.schemas.submission import SubmissionResponse

        self.assertNotIn("ai_feedback", SubmissionResponse.model_fields)

    def test_teacher_feedback_update_schema(self):
        from app.schemas.submission import TeacherFeedbackUpdate

        obj = TeacherFeedbackUpdate(teacher_feedback="写得不错", score=8)
        self.assertEqual(obj.score, 8)


class TestAttachmentAIFeedbackService(unittest.IsolatedAsyncioTestCase):
    async def test_generate_done_on_success(self):
        from app.services.attachment_ai_feedback_service import AttachmentAIFeedbackService

        service = AttachmentAIFeedbackService(AsyncMock())
        attachment = SimpleNamespace(
            id="att-1",
            owner_type="submission",
            owner_id="sub-1",
            management_system_id="ms-1",
            file_url="media/t.jpg",
        )
        service.attachment_repo.get = AsyncMock(return_value=attachment)
        service.submission_repo.get = AsyncMock(return_value=SimpleNamespace(id="sub-1"))
        service.runtime.recognize_char = AsyncMock(return_value="永")
        service.runtime.call_attachment_model = AsyncMock(
            return_value={
                "stroke_score": 7,
                "structure_score": 8,
                "overall_score": 6,
                "summary": "不错",
            }
        )
        service.feedback_repo.upsert_feedback = AsyncMock(return_value=SimpleNamespace(id="fb-1"))

        result = await service.generate("att-1")

        self.assertEqual(result["status"], "done")
        self.assertEqual(
            service.feedback_repo.upsert_feedback.call_args.kwargs["target_type"],
            "submission_attachment",
        )
        self.assertEqual(
            service.feedback_repo.upsert_feedback.call_args.kwargs["result_payload"]["attachment_id"],
            "att-1",
        )

    async def test_generate_failed_on_exception(self):
        from app.services.attachment_ai_feedback_service import AttachmentAIFeedbackService

        service = AttachmentAIFeedbackService(AsyncMock())
        attachment = SimpleNamespace(
            id="att-1",
            owner_type="submission",
            owner_id="sub-1",
            management_system_id="ms-1",
            file_url="media/t.jpg",
        )
        service.attachment_repo.get = AsyncMock(return_value=attachment)
        service.submission_repo.get = AsyncMock(return_value=SimpleNamespace(id="sub-1"))
        service.runtime.recognize_char = AsyncMock(return_value="永")
        service.runtime.call_attachment_model = AsyncMock(side_effect=Exception("vision error"))
        service.feedback_repo.upsert_feedback = AsyncMock(return_value=SimpleNamespace(id="fb-2"))

        result = await service.generate("att-1")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            service.feedback_repo.upsert_feedback.call_args.kwargs["status"],
            "failed",
        )


class TestAIFeedbackTask(unittest.TestCase):
    def test_task_is_registered(self):
        from app.tasks.ai_feedback_tasks import generate_ai_feedback

        self.assertEqual(generate_ai_feedback.name, "generate_ai_feedback")

    def test_celery_registry_contains_key_tasks(self):
        from app.core.celery_app import celery_app

        self.assertIn("send_submission_notification", celery_app.tasks)
        self.assertIn("generate_ai_feedback", celery_app.tasks)
        self.assertIn("generate_submission_ai_summary", celery_app.tasks)
        self.assertIn("process_import_data", celery_app.tasks)

    def test_generate_attachment_feedback_calls_service(self):
        from app.tasks.ai_feedback_tasks import _generate_attachment_feedback
        import asyncio

        with patch("app.tasks.ai_feedback_tasks.AsyncSessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.attachment_ai_feedback_service.AttachmentAIFeedbackService") as mock_svc_cls:
                mock_svc = AsyncMock()
                mock_svc.generate = AsyncMock(return_value={"status": "done", "attachment_id": "att-1"})
                mock_svc_cls.return_value = mock_svc
                result = asyncio.run(_generate_attachment_feedback("att-1"))
        self.assertEqual(result["status"], "done")

    def test_generate_submission_summary_calls_service(self):
        from app.tasks.ai_feedback_tasks import _generate_submission_summary
        import asyncio

        with patch("app.tasks.ai_feedback_tasks.AsyncSessionLocal") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("app.services.submission_ai_summary_service.SubmissionAISummaryService") as mock_svc_cls:
                mock_svc = AsyncMock()
                mock_svc.generate = AsyncMock(return_value={"status": "done", "submission_id": "sub-1"})
                mock_svc_cls.return_value = mock_svc
                result = asyncio.run(_generate_submission_summary("sub-1", "user-1"))
        self.assertEqual(result["status"], "done")


class TestSubmissionServiceUpdates(unittest.IsolatedAsyncioTestCase):
    async def test_grade_writes_teacher_feedback(self):
        from app.schemas.submission import SubmissionGrade
        from app.services.submission_service import SubmissionService

        submission = SimpleNamespace(
            id="sub-1",
            assignment_id="asg-1",
            student_id="stu-1",
            status="submitted",
            score=None,
            teacher_feedback=None,
            ai_feedback=None,
            submitted_at=datetime(2026, 4, 15),
            graded_at=None,
            content=None,
        )
        service = SubmissionService(AsyncMock())
        service.repo.get = AsyncMock(return_value=submission)
        service.repo.update = AsyncMock(return_value=submission)
        service.repo.db = AsyncMock()
        service.repo.db.execute = AsyncMock(
            return_value=AsyncMock(
                scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )
        service.repo.commit = AsyncMock()

        with patch("app.services.submission_service.send_grade_notification") as mock_task:
            mock_task.delay = MagicMock()
            await service.grade_submission(
                "sub-1",
                SubmissionGrade(score=9, feedback="很好"),
                "teacher-1",
            )

        update_data = service.repo.update.call_args[0][1]
        self.assertIn("teacher_feedback", update_data)
        self.assertEqual(update_data["teacher_feedback"], "很好")

    async def test_build_resubmission_payload_does_not_write_legacy_ai_feedback(self):
        from app.services.submission_service import SubmissionService

        payload = SubmissionService._build_resubmission_payload(
            submission_in=SimpleNamespace(content="重新提交"),
            next_status="submitted",
        )

        self.assertNotIn("ai_feedback", payload)

    def test_schedule_followups_dispatches_per_attachment(self):
        from app.services.submission_service import SubmissionService

        with patch("app.services.submission_service.send_submission_notification") as notify_task, patch(
            "app.services.submission_service.generate_ai_feedback"
        ) as feedback_task, patch("app.services.submission_service.publish_outbox_events") as outbox_task:
            notify_task.delay = MagicMock()
            feedback_task.delay = MagicMock()
            outbox_task.delay = MagicMock()

            SubmissionService._schedule_submission_followups(
                "sub-1",
                new_attachment_ids=["att-1", "att-2"],
                publish_outbox=True,
            )

        notify_task.delay.assert_called_once_with("sub-1")
        feedback_task.delay.assert_any_call("att-1")
        feedback_task.delay.assert_any_call("att-2")
        outbox_task.delay.assert_called_once()
