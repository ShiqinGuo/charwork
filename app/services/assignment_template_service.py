from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment_template import AssignmentTemplate
from app.repositories.assignment_template_repo import AssignmentTemplateRepository
from app.schemas.assignment_template import (
    AssignmentTemplateCreate,
    AssignmentTemplateUpdate,
    AssignmentTemplateListResponse,
    AssignmentTemplateResponse,
)


class AssignmentTemplateService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AssignmentTemplateRepository(db)

    async def list_templates(
        self, teacher_id: str, skip: int, limit: int,
    ) -> AssignmentTemplateListResponse:
        items = await self.repo.get_all_by_teacher(teacher_id, skip, limit)
        total = await self.repo.count_by_teacher(teacher_id)
        return AssignmentTemplateListResponse(
            total=total,
            items=[AssignmentTemplateResponse.model_validate(i) for i in items],
        )

    async def create_template(
        self, teacher_id: str, data: AssignmentTemplateCreate,
    ) -> AssignmentTemplateResponse:
        template = AssignmentTemplate(teacher_id=teacher_id, **data.model_dump())
        result = await self.repo.create(template)
        return AssignmentTemplateResponse.model_validate(result)

    async def update_template(
        self, template_id: str, data: AssignmentTemplateUpdate,
    ) -> Optional[AssignmentTemplateResponse]:
        template = await self.repo.get(template_id)
        if not template:
            return None
        updated = await self.repo.update(template, data.model_dump(exclude_unset=True))
        return AssignmentTemplateResponse.model_validate(updated)

    async def delete_template(self, template_id: str) -> bool:
        template = await self.repo.get(template_id)
        if not template:
            return False
        await self.repo.delete(template)
        return True
