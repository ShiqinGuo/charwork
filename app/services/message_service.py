from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.message_repo import MessageRepository
from app.schemas.message import MessageCreate, MessageResponse


class MessageService:
    def __init__(self, db: AsyncSession):
        self.repo = MessageRepository(db)

    async def send_message(self, body: MessageCreate) -> MessageResponse:
        msg = await self.repo.create(body)
        return MessageResponse.model_validate(msg)

    async def list_inbox(self, user_id: str, skip: int = 0, limit: int = 20) -> dict:
        items = await self.repo.list_inbox(user_id, skip, limit)
        return {"items": [MessageResponse.model_validate(i) for i in items]}

    async def list_outbox(self, user_id: str, skip: int = 0, limit: int = 20) -> dict:
        items = await self.repo.list_outbox(user_id, skip, limit)
        return {"items": [MessageResponse.model_validate(i) for i in items]}

    async def mark_read(self, id: str) -> Optional[MessageResponse]:
        msg = await self.repo.get(id)
        if not msg:
            return None
        msg = await self.repo.update(msg, {"is_read": True})
        return MessageResponse.model_validate(msg)
