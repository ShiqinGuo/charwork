import logging
import asyncio

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.repositories.event_outbox_repo import EventOutboxRepository


logger = logging.getLogger(__name__)


@celery_app.task(name="send_submission_notification")
def send_submission_notification(submission_id: str) -> dict:
    logger.info(f"收到作业提交通知任务：submission_id={submission_id}")
    return {"status": "ok", "submission_id": submission_id}


@celery_app.task(name="send_grade_notification")
def send_grade_notification(submission_id: str) -> dict:
    logger.info(f"收到作业批改通知任务：submission_id={submission_id}")
    return {"status": "ok", "submission_id": submission_id}


@celery_app.task(name="batch_send_reminder")
def batch_send_reminder(assignment_id: str) -> dict:
    logger.info(f"收到作业提醒任务：assignment_id={assignment_id}")
    return {"status": "ok", "assignment_id": assignment_id}


async def _publish_outbox_events(limit: int = 100) -> dict:
    async with AsyncSessionLocal() as db:
        repo = EventOutboxRepository(db)
        items = await repo.list_pending(limit)
        published_count = 0
        failed_count = 0
        for event in items:
            try:
                logger.info(
                    "发布 outbox 事件：event_id=%s, type=%s, aggregate_id=%s",
                    event.id,
                    event.event_type,
                    event.aggregate_id,
                )
                await repo.mark_published(event)
                published_count += 1
            except Exception as e:
                await repo.mark_failed(event, str(e))
                failed_count += 1
        await db.commit()
        return {
            "status": "ok",
            "published_count": published_count,
            "failed_count": failed_count,
        }


@celery_app.task(name="publish_outbox_events")
def publish_outbox_events(limit: int = 100) -> dict:
    return asyncio.run(_publish_outbox_events(limit=limit))
