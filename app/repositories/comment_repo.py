from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.schemas.comment import CommentCreate


class CommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_target(self, target_type: str, target_id: str, skip: int = 0, limit: int = 100) -> List[Comment]:
        result = await self.db.execute(
            select(Comment)
            .where(Comment.target_type == target_type, Comment.target_id == target_id)
            .order_by(Comment.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_roots(self, target_type: str, target_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Comment).where(
                Comment.target_type == target_type,
                Comment.target_id == target_id,
                Comment.parent_id.is_(None),
            )
        )
        return result.scalar() or 0

    async def list_roots(self, target_type: str, target_id: str, skip: int = 0, limit: int = 20) -> List[Comment]:
        result = await self.db.execute(
            select(Comment)
            .where(
                Comment.target_type == target_type,
                Comment.target_id == target_id,
                Comment.parent_id.is_(None),
            )
            .order_by(Comment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_replies_by_root_ids(self, root_ids: list[str]) -> List[Comment]:
        if not root_ids:
            return []
        result = await self.db.execute(
            select(Comment)
            .where(Comment.root_id.in_(root_ids), Comment.parent_id.is_not(None))
            .order_by(Comment.created_at.asc())
        )
        return result.scalars().all()

    async def get(self, id: str) -> Optional[Comment]:
        result = await self.db.execute(select(Comment).where(Comment.id == id))
        return result.scalars().first()

    async def create(self, comment_in: CommentCreate) -> Comment:
        comment = Comment(**comment_in.model_dump(exclude_none=True))
        if comment.parent_id:
            parent_comment = await self.get(comment.parent_id)
            if not parent_comment:
                raise ValueError("父评论不存在")
            comment.root_id = parent_comment.root_id or parent_comment.id
            if not comment.reply_to_user_id:
                comment.reply_to_user_id = parent_comment.user_id
            parent_comment.reply_count = parent_comment.reply_count + 1
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def update(self, comment: Comment) -> Comment:
        await self.db.commit()
        await self.db.refresh(comment)
        return comment
