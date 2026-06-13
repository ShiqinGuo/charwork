from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.message import MessageCreate, MessageResponse
from app.services.message_service import MessageService


router = APIRouter()


@router.post("/", response_model=MessageResponse)
async def send_message(
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理消息。

    参数：
        body (MessageCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = MessageService(db)
    try:
        return await service.send_message(
            body,
            sender_id=current_user.id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/")
async def list_messages(
    box: Literal["inbox", "outbox"] = Query("inbox"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询消息列表。

    参数：
        box (Literal["inbox", "outbox"]): Literal["inbox", "outbox"] 类型的数据。
        skip (int): 分页偏移量。
        limit (int): 单次查询的最大返回数量。
        scope (ManagementScope): 管理系统作用域对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = MessageService(db)
    if box == "outbox":
        return await service.list_outbox(current_user.id, skip, limit)
    return await service.list_inbox(current_user.id, skip, limit)


@router.put("/{id}/read", response_model=MessageResponse)
async def mark_read(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理read。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    msg = await MessageService(db).mark_read(id, current_user.id)
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在或无权限")
    return msg
