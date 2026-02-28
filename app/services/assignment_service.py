from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.assignment_repo import AssignmentRepository
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentResponse, AssignmentListResponse


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.repo = AssignmentRepository(db)

    async def get_assignment(self, id: str) -> Optional[AssignmentResponse]:
        assignment = await self.repo.get(id)
        if assignment:
            return AssignmentResponse.model_validate(assignment)
        return None

    async def list_assignments(self, skip: int = 0, limit: int = 20,
                               teacher_id: Optional[str] = None,
                               status: Optional[str] = None) -> AssignmentListResponse:
        items = await self.repo.get_all(skip, limit, teacher_id, status)
        total = await self.repo.count(teacher_id, status)

        return AssignmentListResponse(
            total=total,
            items=[AssignmentResponse.model_validate(item) for item in items]
        )

    async def create_assignment(self, assignment_in: AssignmentCreate, teacher_id: str) -> AssignmentResponse:
        assignment = await self.repo.create(assignment_in, teacher_id)
        return AssignmentResponse.model_validate(assignment)

    async def update_assignment(self, id: str, assignment_in: AssignmentUpdate) -> Optional[AssignmentResponse]:
        assignment = await self.repo.get(id)
        if not assignment:
            return None

        updated_assignment = await self.repo.update(assignment, assignment_in)
        return AssignmentResponse.model_validate(updated_assignment)

    async def delete_assignment(self, id: str) -> bool:
        assignment = await self.repo.get(id)
        if not assignment:
            return False

        await self.repo.delete(assignment)
        return True
