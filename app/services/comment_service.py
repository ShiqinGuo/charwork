"""
为什么这样做：评论根节点在创建后补写 root_id，保证树结构与扁平查询都能稳定复用同一主键锚点。
特殊逻辑：扁平列表先查根再聚合回复，避免分页时回复打散导致上下文丢失。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.comment_repo import CommentRepository
from app.schemas.comment import CommentCreate, CommentResponse, FlatCommentListResponse, FlatCommentItem


class CommentService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CommentService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = CommentRepository(db)

    async def list_comments(
        self, target_type: str, target_id: str, skip: int = 0, limit: int = 20
    ) -> list[CommentResponse]:
        """
        功能描述：
            按条件查询评论列表。

        参数：
            target_type (str): 字符串结果。
            target_id (str): targetID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            list[CommentResponse]: 返回列表形式的结果数据。
        """
        items = await self.repo.list_by_target(target_type, target_id, skip, limit)
        return [CommentResponse.model_validate(i) for i in items]

    async def create_comment(self, body: CommentCreate) -> CommentResponse:
        """
        功能描述：
            创建评论并返回结果。

        参数：
            body (CommentCreate): 接口请求体对象。

        返回值：
            CommentResponse: 返回创建后的结果对象。
        """
        comment = await self.repo.create(body)
        if not comment.parent_id and not comment.root_id:
            comment.root_id = comment.id
            comment = await self.repo.update(comment)
        return CommentResponse.model_validate(comment)

    async def list_flat_comments(
        self, target_type: str, target_id: str, skip: int = 0, limit: int = 20
    ) -> FlatCommentListResponse:
        """
        功能描述：
            按条件查询flat评论列表。

        参数：
            target_type (str): 字符串结果。
            target_id (str): targetID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            FlatCommentListResponse: 返回列表或分页查询结果。
        """
        roots = await self.repo.list_roots(target_type, target_id, skip, limit)
        total = await self.repo.count_roots(target_type, target_id)
        root_ids = [i.id for i in roots]
        replies = await self.repo.list_replies_by_root_ids(root_ids)
        reply_group: dict[str, list] = {root_id: [] for root_id in root_ids}
        for reply in replies:
            if reply.root_id in reply_group:
                reply_group[reply.root_id].append(reply)
        items = [
            FlatCommentItem(
                root=CommentResponse.model_validate(root),
                replies=[CommentResponse.model_validate(reply) for reply in reply_group.get(root.id, [])],
            )
            for root in roots
        ]
        return FlatCommentListResponse(total=total, items=items)
