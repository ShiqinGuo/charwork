from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.schemas.comment import CommentCreate


class CommentRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CommentRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def list_by_target(self, target_type: str, target_id: str, skip: int = 0, limit: int = 100) -> List[Comment]:
        """
        功能描述：
            按条件查询bytarget列表。

        参数：
            target_type (str): 字符串结果。
            target_id (str): targetID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            List[Comment]: 返回列表或分页查询结果。
        """
        result = await self.db.execute(
            select(Comment)
            .where(Comment.target_type == target_type, Comment.target_id == target_id)
            .order_by(Comment.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_roots(self, target_type: str, target_id: str) -> int:
        """
        功能描述：
            统计roots数量。

        参数：
            target_type (str): 字符串结果。
            target_id (str): targetID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(Comment).where(
                Comment.target_type == target_type,
                Comment.target_id == target_id,
                Comment.parent_id.is_(None),
            )
        )
        return result.scalar() or 0

    async def list_roots(self, target_type: str, target_id: str, skip: int = 0, limit: int = 20) -> List[Comment]:
        """
        功能描述：
            按条件查询roots列表。

        参数：
            target_type (str): 字符串结果。
            target_id (str): targetID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            List[Comment]: 返回列表或分页查询结果。
        """
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
        """
        功能描述：
            按条件查询repliesbyroot标识列表列表。

        参数：
            root_ids (list[str]): rootID列表。

        返回值：
            List[Comment]: 返回列表或分页查询结果。
        """
        if not root_ids:
            return []
        result = await self.db.execute(
            select(Comment)
            .where(Comment.root_id.in_(root_ids), Comment.parent_id.is_not(None))
            .order_by(Comment.created_at.asc())
        )
        return result.scalars().all()

    async def get(self, id: str) -> Optional[Comment]:
        """
        功能描述：
            获取CommentRepository。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[Comment]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(Comment).where(Comment.id == id))
        return result.scalars().first()

    async def create(self, comment_in: CommentCreate) -> Comment:
        """
        功能描述：
            创建CommentRepository。

        参数：
            comment_in (CommentCreate): 评论输入对象。

        返回值：
            Comment: 返回Comment类型的处理结果。
        """
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
        """
        功能描述：
            更新CommentRepository。

        参数：
            comment (Comment): Comment 类型的数据。

        返回值：
            Comment: 返回Comment类型的处理结果。
        """
        await self.db.commit()
        await self.db.refresh(comment)
        return comment
