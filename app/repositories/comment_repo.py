from typing import List
from sqlalchemy import select
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
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def create(self, comment_in: CommentCreate) -> Comment:
        comment = Comment(**comment_in.model_dump())
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment
