import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_feedback import (
    AIFeedbackGeneratedBy,
    AIFeedbackScope,
    AIFeedbackStatus,
    AIFeedbackTargetType,
    AIFeedbackVisibility,
)
from app.repositories.ai_feedback_repo import AIFeedbackRepository
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.submission_repo import SubmissionRepository
from app.services.ai_feedback_runtime import AIFeedbackRuntime


logger = logging.getLogger(__name__)


class SubmissionAISummaryService:
    def __init__(self, db: AsyncSession):
        self.submission_repo = SubmissionRepository(db)
        self.attachment_repo = AttachmentRepository(db)
        self.student_repo = StudentRepository(db)
        self.feedback_repo = AIFeedbackRepository(db)
        self.runtime = AIFeedbackRuntime()

    async def generate(self, submission_id: str, student_user_id: str) -> dict:
        submission = await self.submission_repo.get(submission_id)
        if not submission:
            logger.warning("generate_submission_ai_summary: submission %s 不存在", submission_id)
            return {"status": "missing", "submission_id": submission_id}

        student = await self.student_repo.get(submission.student_id)
        if not student or student.user_id != student_user_id:
            logger.warning("generate_submission_ai_summary: submission %s 权限不匹配", submission_id)
            return {"status": "forbidden", "submission_id": submission_id}

        attachments = await self.attachment_repo.get_by_owner(
            owner_type="submission",
            owner_id=submission_id,
        )
        attachment_ids = [attachment.id for attachment in attachments]
        feedbacks = await self.feedback_repo.list_by_targets(
            target_type=AIFeedbackTargetType.SUBMISSION_ATTACHMENT.value,
            target_ids=attachment_ids,
            feedback_scope=AIFeedbackScope.ATTACHMENT_ITEM.value,
            visibility_scopes=[AIFeedbackVisibility.SHARED_TEACHER_STUDENT.value],
        )
        done_items = [
            feedback.result_payload
            for feedback in feedbacks
            if feedback.status == AIFeedbackStatus.DONE.value and feedback.result_payload
        ]

        if not done_items:
            payload = {
                "submission_id": submission_id,
                "attachment_count": len(attachments),
                "summary": "暂无可汇总的附件评价",
                "strengths": [],
                "improvements": [],
                "overall_level": None,
            }
            feedback = await self.feedback_repo.upsert_feedback(
                target_type=AIFeedbackTargetType.SUBMISSION.value,
                target_id=submission_id,
                feedback_scope=AIFeedbackScope.STUDENT_SUMMARY.value,
                visibility_scope=AIFeedbackVisibility.STUDENT_ONLY.value,
                status=AIFeedbackStatus.FAILED.value,
                generated_by=AIFeedbackGeneratedBy.STUDENT.value,
                result_payload=payload,
            )
            return {"status": feedback.status, "submission_id": submission_id, "feedback_id": feedback.id}

        try:
            summary = await self.runtime.call_summary_model(done_items)
            payload = {
                "submission_id": submission_id,
                "attachment_count": len(done_items),
                "summary": summary.get("summary", ""),
                "strengths": summary.get("strengths", []) or [],
                "improvements": summary.get("improvements", []) or [],
                "overall_level": summary.get("overall_level"),
            }
            feedback = await self.feedback_repo.upsert_feedback(
                target_type=AIFeedbackTargetType.SUBMISSION.value,
                target_id=submission_id,
                feedback_scope=AIFeedbackScope.STUDENT_SUMMARY.value,
                visibility_scope=AIFeedbackVisibility.STUDENT_ONLY.value,
                status=AIFeedbackStatus.DONE.value,
                generated_by=AIFeedbackGeneratedBy.STUDENT.value,
                result_payload=payload,
            )
            return {"status": feedback.status, "submission_id": submission_id, "feedback_id": feedback.id}
        except Exception as exc:
            logger.error("学生 AI 总评生成失败 submission=%s: %s", submission_id, exc)
            payload = {
                "submission_id": submission_id,
                "attachment_count": len(done_items),
                "summary": "AI 总评生成失败",
                "strengths": [],
                "improvements": [],
                "overall_level": None,
            }
            feedback = await self.feedback_repo.upsert_feedback(
                target_type=AIFeedbackTargetType.SUBMISSION.value,
                target_id=submission_id,
                feedback_scope=AIFeedbackScope.STUDENT_SUMMARY.value,
                visibility_scope=AIFeedbackVisibility.STUDENT_ONLY.value,
                status=AIFeedbackStatus.FAILED.value,
                generated_by=AIFeedbackGeneratedBy.STUDENT.value,
                result_payload=payload,
            )
            return {"status": feedback.status, "submission_id": submission_id, "feedback_id": feedback.id}
