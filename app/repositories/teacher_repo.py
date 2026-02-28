from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate


class TeacherRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Teacher]:
        result = await self.db.execute(select(Teacher).where(Teacher.id == id))
        return result.scalars().first()

    async def get_by_user_id(self, user_id: str) -> Optional[Teacher]:
        result = await self.db.execute(select(Teacher).where(Teacher.user_id == user_id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Teacher]:
        result = await self.db.execute(select(Teacher).offset(skip).limit(limit))
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Teacher))
        return result.scalar()

    async def create(self, teacher_in: TeacherCreate) -> Teacher:
        teacher = Teacher(**teacher_in.model_dump())
        self.db.add(teacher)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def update(self, teacher: Teacher, teacher_in: TeacherUpdate) -> Teacher:
        update_data = teacher_in.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(teacher, k, v)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def delete(self, teacher: Teacher) -> None:
        await self.db.delete(teacher)
        await self.db.commit()
