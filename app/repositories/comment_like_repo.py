from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment_like import CommentLike


class CommentLikeRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CommentLikeRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def create(self, comment_id: str, user_id: str) -> CommentLike:
        """
        功能描述：
            创建CommentLikeRepository。

        参数：
            comment_id (str): 评论ID。
            user_id (str): 用户ID。

        返回值：
            CommentLike: 返回CommentLike类型的处理结果。
        """
        entity = CommentLike(comment_id=comment_id, user_id=user_id)
        self.db.add(entity)
        return entity

    async def delete(self, comment_id: str, user_id: str) -> None:
        """
        功能描述：
            删除CommentLikeRepository。

        参数：
            comment_id (str): 评论ID。
            user_id (str): 用户ID。

        返回值：
            None: 无返回值。
        """
        await self.db.execute(
            delete(CommentLike).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id)
        )

    async def exists(self, comment_id: str, user_id: str) -> bool:
        """
        功能描述：
            处理CommentLikeRepository。

        参数：
            comment_id (str): 评论ID。
            user_id (str): 用户ID。

        返回值：
            bool: 返回操作是否成功。
        """
        result = await self.db.execute(
            select(CommentLike.id).where(CommentLike.comment_id == comment_id, CommentLike.user_id == user_id)
        )
        return result.scalar() is not None
