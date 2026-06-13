import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="generate_ai_feedback")
def generate_ai_feedback(attachment_id: str) -> dict:
    """
    功能描述：
        异步生成单附件 AI 评语，由附件成功关联提交后触发。

    参数：
        attachment_id (str): 附件ID。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    logger.info("开始生成附件 AI 评语：attachment_id=%s", attachment_id)
    return asyncio.run(_generate_attachment_feedback(attachment_id))


@celery_app.task(name="generate_submission_ai_summary")
def generate_submission_ai_summary(submission_id: str, student_user_id: str) -> dict:
    """
    功能描述：
        异步生成学生主动触发的提交总评。

    参数：
        submission_id (str): 提交记录ID。
        student_user_id (str): 学生用户ID。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    logger.info(
        "开始生成学生 AI 总评：submission_id=%s, student_user_id=%s",
        submission_id,
        student_user_id,
    )
    return asyncio.run(_generate_submission_summary(submission_id, student_user_id))


async def _generate_attachment_feedback(attachment_id: str) -> dict:
    from app.services.attachment_ai_feedback_service import AttachmentAIFeedbackService

    try:
        async with AsyncSessionLocal() as db:
            return await AttachmentAIFeedbackService(db).generate(attachment_id)
    except Exception as exc:
        logger.error("generate_ai_feedback task 异常 attachment=%s: %s", attachment_id, exc)
    return {"status": "failed", "attachment_id": attachment_id}


async def _generate_submission_summary(submission_id: str, student_user_id: str) -> dict:
    from app.services.submission_ai_summary_service import SubmissionAISummaryService

    try:
        async with AsyncSessionLocal() as db:
            return await SubmissionAISummaryService(db).generate(submission_id, student_user_id)
    except Exception as exc:
        logger.error("generate_submission_ai_summary task 异常 submission=%s: %s", submission_id, exc)
    return {"status": "failed", "submission_id": submission_id}
