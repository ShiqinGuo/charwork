from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import AssignmentStatus
from app.repositories.assignment_repo import AssignmentRepository
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    AssignmentListResponse,
    AssignmentTransitionEvent,
    AssignmentTransitionResponse,
)
from app.services.assignment_state_machine import AssignmentStateMachine


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.repo = AssignmentRepository(db)
        self.state_machine = AssignmentStateMachine()

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

    async def transition_assignment(
        self,
        id: str,
        event: AssignmentTransitionEvent,
    ) -> Optional[AssignmentTransitionResponse]:
        assignment = await self.repo.get(id)
        if not assignment:
            return None
        from_status = AssignmentStatus(assignment.status)
        transition_result = self.state_machine.transition(from_status, event)
        assignment.status = transition_result.to_status
        await self.repo.commit_and_refresh(assignment)
        return AssignmentTransitionResponse(
            assignment=AssignmentResponse.model_validate(assignment),
            from_status=transition_result.from_status,
            to_status=transition_result.to_status,
            event=transition_result.event,
        )

    async def reach_deadline_assignments(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now()
        items = await self.repo.list_published_due(now)
        affected = 0
        for assignment in items:
            transition_result = self.state_machine.transition(
                AssignmentStatus(assignment.status),
                AssignmentTransitionEvent.REACH_DEADLINE,
            )
            assignment.status = transition_result.to_status
            affected += 1
        if affected:
            await self.repo.commit()
        return affected
