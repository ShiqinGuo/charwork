from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment_like import CommentLike


class CommentLikeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, comment_id: str, user_id: str) -> CommentLike:
        entity = CommentLike(comment_id=comment_id, user_id=user_id)
        self.db.add(entity)
        return entity

    async def delete(self, comment_id: str, user_id: str) -> None:
        await self.db.execute(
            delete(CommentLike).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id)
        )

    async def exists(self, comment_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(CommentLike.id).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id)
        )
        return result.scalar() is not None
