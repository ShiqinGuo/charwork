from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.comment_repo import CommentRepository
from app.schemas.comment import CommentCreate, CommentResponse


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
        return CommentResponse.model_validate(comment)
