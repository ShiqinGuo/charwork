from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_outbox import EventOutbox, OutboxStatus


class EventOutboxRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化EventOutboxRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def add_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: str,
    ) -> EventOutbox:
        """
        功能描述：
            新增事件。

        参数：
            aggregate_type (str): 字符串结果。
            aggregate_id (str): aggregateID。
            event_type (str): 字符串结果。
            payload (str): 待处理的原始数据载荷。

        返回值：
            EventOutbox: 返回EventOutbox类型的处理结果。
        """
        event = EventOutbox(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            status=OutboxStatus.PENDING,
        )
        self.db.add(event)
        return event

    async def list_pending(self, limit: int = 100) -> List[EventOutbox]:
        """
        功能描述：
            按条件查询pending列表。

        参数：
            limit (int): 单次查询的最大返回数量。

        返回值：
            List[EventOutbox]: 返回列表或分页查询结果。
        """
        result = await self.db.execute(
            select(EventOutbox)
            .where(EventOutbox.status == OutboxStatus.PENDING)
            .order_by(EventOutbox.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def mark_published(self, event: EventOutbox) -> None:
        """
        功能描述：
            处理published。

        参数：
            event (EventOutbox): EventOutbox 类型的数据。

        返回值：
            None: 无返回值。
        """
        event.status = OutboxStatus.PUBLISHED
        event.error_message = None
        event.published_at = datetime.now()

    async def mark_failed(self, event: EventOutbox, error_message: str) -> None:
        """
        功能描述：
            处理failed。

        参数：
            event (EventOutbox): EventOutbox 类型的数据。
            error_message (str): 字符串结果。

        返回值：
            None: 无返回值。
        """
        event.status = OutboxStatus.FAILED
        event.retry_count = event.retry_count + 1
        event.error_message = error_message
