from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.services.message_service import MessageService


router = APIRouter()


@router.post("/", response_model=MessageResponse)
async def send_message(body: MessageCreate, db: AsyncSession = Depends(get_db)):
    return await MessageService(db).send_message(body)


@router.get("/")
async def list_messages(
    user_id: str = Query(...),
    box: Literal["inbox", "outbox"] = Query("inbox"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = MessageService(db)
    if box == "outbox":
        return await service.list_outbox(user_id, skip, limit)
    return await service.list_inbox(user_id, skip, limit)


@router.put("/{id}/read", response_model=MessageResponse)
async def mark_read(id: str, db: AsyncSession = Depends(get_db)):
    msg = await MessageService(db).mark_read(id)
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")
    return msg
