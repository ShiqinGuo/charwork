from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.schemas.message import MessageCreate


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Message]:
        result = await self.db.execute(select(Message).where(Message.id == id))
        return result.scalars().first()

    async def list_inbox(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Message]:
        result = await self.db.execute(
            select(Message).where(Message.receiver_id == user_id).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def list_outbox(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Message]:
        result = await self.db.execute(
            select(Message).where(Message.sender_id == user_id).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, msg_in: MessageCreate) -> Message:
        msg = Message(**msg_in.model_dump())
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def update(self, msg: Message, update_data: dict) -> Message:
        for k, v in update_data.items():
            setattr(msg, k, v)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg
