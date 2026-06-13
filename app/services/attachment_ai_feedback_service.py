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
from app.repositories.submission_repo import SubmissionRepository
from app.services.ai_feedback_runtime import AIFeedbackRuntime


logger = logging.getLogger(__name__)


class AttachmentAIFeedbackService:
    def __init__(self, db: AsyncSession):
        self.attachment_repo = AttachmentRepository(db)
        self.submission_repo = SubmissionRepository(db)
        self.feedback_repo = AIFeedbackRepository(db)
        self.runtime = AIFeedbackRuntime()

    async def generate(self, attachment_id: str) -> dict:
        attachment = await self.attachment_repo.get(attachment_id)
        if not attachment:
            logger.warning("generate_attachment_ai_feedback: attachment %s 不存在", attachment_id)
            return {"status": "missing", "attachment_id": attachment_id}
        if attachment.owner_type != "submission" or attachment.owner_id == "temp":
            logger.warning("generate_attachment_ai_feedback: attachment %s 尚未关联提交", attachment_id)
            return {"status": "skipped", "attachment_id": attachment_id}

        submission = await self.submission_repo.get(attachment.owner_id)
        if not submission:
            logger.warning("generate_attachment_ai_feedback: submission %s 不存在", attachment.owner_id)
            return {"status": "missing_submission", "attachment_id": attachment_id}

        try:
            ocr_text = await self.runtime.recognize_char(attachment.file_url)
            scores = await self.runtime.call_attachment_model(attachment.file_url, ocr_text)
            payload = {
                "attachment_id": attachment.id,
                "char": ocr_text,
                "ocr_text": ocr_text,
                # 新四维度字段（兼容旧字段名 fallback）
                "stroke_quality": scores.get("stroke_quality") or scores.get("stroke_score"),
                "structure_balance": scores.get("structure_balance") or scores.get("structure_score"),
                "layout_placement": scores.get("layout_placement") or scores.get("overall_score"),
                "aesthetic_appeal": scores.get("aesthetic_appeal") or 0,
                # 保留旧字段兼容旧 UI
                "stroke_score": scores.get("stroke_score") or scores.get("stroke_quality"),
                "structure_score": scores.get("structure_score") or scores.get("structure_balance"),
                "overall_score": scores.get("overall_score") or scores.get("layout_placement"),
                "summary": scores.get("summary", ""),
            }
            feedback = await self.feedback_repo.upsert_feedback(
                target_type=AIFeedbackTargetType.SUBMISSION_ATTACHMENT.value,
                target_id=attachment.id,
                feedback_scope=AIFeedbackScope.ATTACHMENT_ITEM.value,
                visibility_scope=AIFeedbackVisibility.SHARED_TEACHER_STUDENT.value,
                status=AIFeedbackStatus.DONE.value,
                generated_by=AIFeedbackGeneratedBy.SYSTEM.value,
                result_payload=payload,
            )
            return {"status": AIFeedbackStatus.DONE.value, "attachment_id": attachment.id, "feedback_id": feedback.id}
        except Exception as exc:
            logger.error("附件 AI 评价生成失败 attachment=%s: %s", attachment.id, exc)
            feedback = await self.feedback_repo.upsert_feedback(
                target_type=AIFeedbackTargetType.SUBMISSION_ATTACHMENT.value,
                target_id=attachment.id,
                feedback_scope=AIFeedbackScope.ATTACHMENT_ITEM.value,
                visibility_scope=AIFeedbackVisibility.SHARED_TEACHER_STUDENT.value,
                status=AIFeedbackStatus.FAILED.value,
                generated_by=AIFeedbackGeneratedBy.SYSTEM.value,
                result_payload={"attachment_id": attachment.id, "summary": ""},
            )
            return {"status": AIFeedbackStatus.FAILED.value, "attachment_id": attachment.id, "feedback_id": feedback.id}
