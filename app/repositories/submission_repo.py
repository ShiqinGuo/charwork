from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission
from app.schemas.submission import SubmissionCreate


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Submission]:
        result = await self.db.execute(select(Submission).where(Submission.id == id))
        return result.scalars().first()

    async def get_all_by_assignment(self, assignment_id: str, skip: int = 0, limit: int = 100) -> List[Submission]:
        result = await self.db.execute(
            select(Submission).where(Submission.assignment_id == assignment_id).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count_by_assignment(self, assignment_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Submission).where(Submission.assignment_id == assignment_id)
        )
        return result.scalar()

    async def create(self, assignment_id: str, submission_in: SubmissionCreate) -> Submission:
        submission = Submission(
            assignment_id=assignment_id,
            student_id=submission_in.student_id,
            content=submission_in.content,
            image_paths=submission_in.image_paths,
        )
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def update(self, submission: Submission, update_data: dict) -> Submission:
        for k, v in update_data.items():
            setattr(submission, k, v)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission
