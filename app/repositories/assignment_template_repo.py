from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment_template import AssignmentTemplate


class AssignmentTemplateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all_by_teacher(
        self, teacher_id: str, skip: int = 0, limit: int = 20,
    ) -> List[AssignmentTemplate]:
        result = await self.db.execute(
            select(AssignmentTemplate)
            .where(AssignmentTemplate.teacher_id == teacher_id)
            .order_by(AssignmentTemplate.updated_at.desc())
            .offset(skip).limit(limit),
        )
        return result.scalars().all()

    async def count_by_teacher(self, teacher_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(AssignmentTemplate)
            .where(AssignmentTemplate.teacher_id == teacher_id),
        )
        return result.scalar()

    async def get(self, template_id: str) -> Optional[AssignmentTemplate]:
        return await self.db.get(AssignmentTemplate, template_id)

    async def create(self, template: AssignmentTemplate) -> AssignmentTemplate:
        self.db.add(template)
        await self.db.flush()
        return template

    async def update(self, template: AssignmentTemplate, data: dict) -> AssignmentTemplate:
        for k, v in data.items():
            if v is not None:
                setattr(template, k, v)
        await self.db.flush()
        return template

    async def delete(self, template: AssignmentTemplate) -> None:
        await self.db.delete(template)
        await self.db.flush()
