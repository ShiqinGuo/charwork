from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.assignment import Assignment
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate


class AssignmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Assignment]:
        result = await self.db.execute(select(Assignment).where(Assignment.id == id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100,
                      teacher_id: Optional[str] = None,
                      status: Optional[str] = None) -> List[Assignment]:
        query = select(Assignment)

        if teacher_id:
            query = query.where(Assignment.teacher_id == teacher_id)
        if status:
            query = query.where(Assignment.status == status)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, teacher_id: Optional[str] = None,
                    status: Optional[str] = None) -> int:
        query = select(func.count()).select_from(Assignment)

        if teacher_id:
            query = query.where(Assignment.teacher_id == teacher_id)
        if status:
            query = query.where(Assignment.status == status)

        result = await self.db.execute(query)
        return result.scalar()

    async def create(self, assignment_in: AssignmentCreate, teacher_id: str) -> Assignment:
        assignment = Assignment(**assignment_in.model_dump(), teacher_id=teacher_id)
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def update(self, assignment: Assignment, assignment_in: AssignmentUpdate) -> Assignment:
        update_data = assignment_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(assignment, key, value)

        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def delete(self, assignment: Assignment) -> None:
        await self.db.delete(assignment)
        await self.db.commit()
