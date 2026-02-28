from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.teacher_repo import TeacherRepository
from app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherResponse


class TeacherService:
    def __init__(self, db: AsyncSession):
        self.repo = TeacherRepository(db)

    async def get_teacher(self, id: str) -> Optional[TeacherResponse]:
        teacher = await self.repo.get(id)
        return TeacherResponse.model_validate(teacher) if teacher else None

    async def list_teachers(self, skip: int = 0, limit: int = 20) -> dict:
        items = await self.repo.get_all(skip, limit)
        total = await self.repo.count()
        return {
            "total": total,
            "items": [TeacherResponse.model_validate(i) for i in items],
        }

    async def create_teacher(self, teacher_in: TeacherCreate) -> TeacherResponse:
        teacher = await self.repo.create(teacher_in)
        return TeacherResponse.model_validate(teacher)

    async def update_teacher(self, id: str, teacher_in: TeacherUpdate) -> Optional[TeacherResponse]:
        teacher = await self.repo.get(id)
        if not teacher:
            return None
        teacher = await self.repo.update(teacher, teacher_in)
        return TeacherResponse.model_validate(teacher)

    async def delete_teacher(self, id: str) -> bool:
        teacher = await self.repo.get(id)
        if not teacher:
            return False
        await self.repo.delete(teacher)
        return True
