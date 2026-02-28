import logging
from app.core.celery_app import celery_app


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
