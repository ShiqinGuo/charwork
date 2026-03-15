from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.comment import (
    CommentCreate,
    CommentResponse,
    TargetType,
    FlatCommentListResponse,
    CommentLikeRequest,
    CommentLikeResponse,
)
from app.services.comment_like_service import CommentLikeService
from app.services.comment_service import CommentService


router = APIRouter()


@router.get("/", response_model=list[CommentResponse])
async def list_comments(
    target_type: TargetType = Query(...),
    target_id: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await CommentService(db).list_comments(target_type.value, target_id, skip, limit)


@router.post("/", response_model=CommentResponse)
async def create_comment(body: CommentCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await CommentService(db).create_comment(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"发表评论失败：{str(e)}")


@router.get("/flat", response_model=FlatCommentListResponse)
async def list_flat_comments(
    target_type: TargetType = Query(...),
    target_id: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await CommentService(db).list_flat_comments(target_type.value, target_id, skip, limit)


@router.post("/{comment_id}/likes", response_model=CommentLikeResponse)
async def like_comment(comment_id: str, body: CommentLikeRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await CommentLikeService(db).operate_like(comment_id, body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"点赞操作失败：{str(e)}")
