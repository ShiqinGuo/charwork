from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.comment_repo import CommentRepository
from app.schemas.comment import CommentCreate, CommentResponse, FlatCommentListResponse, FlatCommentItem


class CommentService:
    def __init__(self, db: AsyncSession):
        self.repo = CommentRepository(db)

    async def list_comments(
        self, target_type: str, target_id: str, skip: int = 0, limit: int = 20
            ) -> list[CommentResponse]:
        items = await self.repo.list_by_target(target_type, target_id, skip, limit)
        return [CommentResponse.model_validate(i) for i in items]

    async def create_comment(self, body: CommentCreate) -> CommentResponse:
        comment = await self.repo.create(body)
        if not comment.parent_id and not comment.root_id:
            comment.root_id = comment.id
            comment = await self.repo.update(comment)
        return CommentResponse.model_validate(comment)

    async def list_flat_comments(
        self, target_type: str, target_id: str, skip: int = 0, limit: int = 20
    ) -> FlatCommentListResponse:
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
