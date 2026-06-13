import logging
import asyncio

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.repositories.event_outbox_repo import EventOutboxRepository


logger = logging.getLogger(__name__)
TASK_OK_STATUS = "ok"


def _build_task_result(**payload: int | str) -> dict[str, int | str]:
    """
    功能描述：
        构建任务结果。

    参数：
        payload (int | str): 待处理的原始数据载荷。

    返回值：
        dict[str, int | str]: 返回字典形式的结果数据。
    """
    return {"status": TASK_OK_STATUS, **payload}


@celery_app.task(name="send_submission_notification")
def send_submission_notification(submission_id: str) -> dict:
    """
    功能描述：
        处理提交记录通知。

    参数：
        submission_id (str): 提交记录ID。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    logger.info(f"收到作业提交通知任务：submission_id={submission_id}")
    return _build_task_result(submission_id=submission_id)


@celery_app.task(name="send_grade_notification")
def send_grade_notification(submission_id: str) -> dict:
    """
    功能描述：
        处理评分通知。

    参数：
        submission_id (str): 提交记录ID。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    logger.info(f"收到作业批改通知任务：submission_id={submission_id}")
    return _build_task_result(submission_id=submission_id)


@celery_app.task(name="batch_send_reminder")
def batch_send_reminder(plan_id: str, sender_user_id: str, expected_version: int) -> dict:
    """
    功能描述：
        批量处理send提醒。

    参数：
        plan_id (str): 计划ID。
        sender_user_id (str): 发送者用户ID。
        expected_version (int): 整数结果。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    logger.info(
        "收到作业提醒任务：plan_id=%s, expected_version=%s",
        plan_id,
        expected_version,
    )
    # 任务执行器是同步上下文，通过 asyncio.run 串接异步服务层逻辑。
    return asyncio.run(
        _batch_send_reminder(
            plan_id=plan_id,
            sender_user_id=sender_user_id,
            expected_version=expected_version,
        )
    )


async def _batch_send_reminder(
    plan_id: str,
    sender_user_id: str,
    expected_version: int,
) -> dict:
    # 延迟导入避免任务模块与服务模块在启动阶段形成重依赖链。
    """
    功能描述：
        批量处理send提醒。

    参数：
        plan_id (str): 计划ID。
        sender_user_id (str): 发送者用户ID。
        expected_version (int): 整数结果。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    from app.services.assignment_reminder_service import AssignmentReminderService

    async with AsyncSessionLocal() as db:
        result = await AssignmentReminderService(db).execute_plan(
            plan_id=plan_id,
            sender_user_id=sender_user_id,
            expected_version=expected_version,
        )
        return _build_task_result(plan_id=plan_id, executed=result.total)


async def _publish_outbox_events(limit: int = 100) -> dict:
    """
    功能描述：
        发布outboxevents。

    参数：
        limit (int): 单次查询的最大返回数量。

    返回值：
        dict: 返回字典形式的结果数据。
    """
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
            except Exception as exc:
                # 单条失败不阻断批次，记录失败状态后继续处理剩余事件。
                await repo.mark_failed(event, str(exc))
                failed_count += 1
        await db.commit()
        return _build_task_result(
            published_count=published_count,
            failed_count=failed_count,
        )


@celery_app.task(name="publish_outbox_events")
def publish_outbox_events(limit: int = 100) -> dict:
    """
    功能描述：
        发布outboxevents。

    参数：
        limit (int): 单次查询的最大返回数量。

    返回值：
        dict: 返回字典形式的结果数据。
    """
    return asyncio.run(_publish_outbox_events(limit=limit))
