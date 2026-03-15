from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_outbox import EventOutbox, OutboxStatus


class EventOutboxRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: str,
    ) -> EventOutbox:
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
        result = await self.db.execute(
            select(EventOutbox)
            .where(EventOutbox.status == OutboxStatus.PENDING)
            .order_by(EventOutbox.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def mark_published(self, event: EventOutbox) -> None:
        event.status = OutboxStatus.PUBLISHED
        event.error_message = None
        event.published_at = datetime.now()

    async def mark_failed(self, event: EventOutbox, error_message: str) -> None:
        event.status = OutboxStatus.FAILED
        event.retry_count = event.retry_count + 1
        event.error_message = error_message
