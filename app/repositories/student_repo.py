from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


class StudentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Student]:
        result = await self.db.execute(select(Student).where(Student.id == id))
        return result.scalars().first()

    async def get_by_user_id(self, user_id: str) -> Optional[Student]:
        result = await self.db.execute(select(Student).where(Student.user_id == user_id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Student]:
        result = await self.db.execute(select(Student).offset(skip).limit(limit))
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Student))
        return result.scalar()

    async def create(self, student_in: StudentCreate) -> Student:
        student = Student(**student_in.model_dump())
        self.db.add(student)
        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def update(self, student: Student, student_in: StudentUpdate) -> Student:
        update_data = student_in.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(student, k, v)
        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def delete(self, student: Student) -> None:
        await self.db.delete(student)
        await self.db.commit()
