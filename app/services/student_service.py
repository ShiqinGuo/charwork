from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.student_repo import StudentRepository
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse


class StudentService:
    def __init__(self, db: AsyncSession):
        self.repo = StudentRepository(db)

    async def get_student(self, id: str) -> Optional[StudentResponse]:
        student = await self.repo.get(id)
        return StudentResponse.model_validate(student) if student else None

    async def list_students(self, skip: int = 0, limit: int = 20) -> dict:
        items = await self.repo.get_all(skip, limit)
        total = await self.repo.count()
        return {
            "total": total,
            "items": [StudentResponse.model_validate(i) for i in items],
        }

    async def create_student(self, student_in: StudentCreate) -> StudentResponse:
        student = await self.repo.create(student_in)
        return StudentResponse.model_validate(student)

    async def update_student(self, id: str, student_in: StudentUpdate) -> Optional[StudentResponse]:
        student = await self.repo.get(id)
        if not student:
            return None
        student = await self.repo.update(student, student_in)
        return StudentResponse.model_validate(student)

    async def delete_student(self, id: str) -> bool:
        student = await self.repo.get(id)
        if not student:
            return False
        await self.repo.delete(student)
        return True
