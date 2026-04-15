import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="generate_ai_feedback")
def generate_ai_feedback(submission_id: str) -> dict:
    """异步生成手写体 AI 评语，由提交创建后触发。"""
    logger.info("开始生成 AI 评语：submission_id=%s", submission_id)
    return asyncio.run(_generate(submission_id))


async def _generate(submission_id: str) -> dict:
    # 延迟导入避免循环依赖
    from app.services.ai_feedback_service import AIFeedbackService

    async with AsyncSessionLocal() as db:
        await AIFeedbackService(db).generate(submission_id)
    return {"status": "ok", "submission_id": submission_id}
