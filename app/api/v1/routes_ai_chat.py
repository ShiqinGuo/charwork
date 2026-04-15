from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher
from app.core.database import get_db
from app.core.management_scope import ManagementScope, get_management_scope
from app.models.teacher import Teacher
from app.schemas.ai_chat import (
    AIChatConversation,
    AIChatConversationListResponse,
    AIChatConversationRenameRequest,
    AIChatMessageListResponse,
    AIChatRequest,
)
from app.services.ai_chat_service import AIChatService
from app.utils.pagination import resolve_pagination


router = APIRouter()


@router.post("/stream")
async def stream_ai_chat(
    body: AIChatRequest,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = AIChatService(db)
    try:
        return StreamingResponse(
            service.stream_chat(body, scope.management_system_id, current_teacher.user_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/conversations", response_model=AIChatConversationListResponse)
async def list_ai_chat_conversations(
    skip: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    page: int | None = Query(None, ge=1),
    size: int | None = Query(None, ge=1, le=100),
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = AIChatService(db)
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit, default_limit=30)
    return await service.list_conversations(
        current_teacher.user_id,
        scope.management_system_id,
        limit=pagination["limit"],
        offset=pagination["skip"],
        page=pagination["page"],
        size=pagination["size"],
    )


@router.get("/conversations/{conversation_id}/messages", response_model=AIChatMessageListResponse)
async def list_ai_chat_messages(
    conversation_id: str,
    skip: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=1, le=500),
    page: int | None = Query(None, ge=1),
    size: int | None = Query(None, ge=1, le=500),
    _scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = AIChatService(db)
    try:
        pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit, default_limit=100, max_limit=500)
        return await service.list_messages(
            conversation_id=conversation_id,
            teacher_user_id=current_teacher.user_id,
            management_system_id=_scope.management_system_id,
            limit=pagination["limit"],
            offset=pagination["skip"],
            page=pagination["page"],
            size=pagination["size"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/conversations/{conversation_id}", response_model=AIChatConversation)
async def rename_ai_chat_conversation(
    conversation_id: str,
    body: AIChatConversationRenameRequest,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = AIChatService(db)
    try:
        return await service.rename_conversation(
            conversation_id=conversation_id,
            teacher_user_id=current_teacher.user_id,
            management_system_id=scope.management_system_id,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/conversations/{conversation_id}")
async def delete_ai_chat_conversation(
    conversation_id: str,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = AIChatService(db)
    try:
        await service.delete_conversation(
            conversation_id=conversation_id,
            teacher_user_id=current_teacher.user_id,
            management_system_id=scope.management_system_id,
        )
        return {"status": "success"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
