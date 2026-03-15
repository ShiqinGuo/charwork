from dataclasses import dataclass
from typing import Dict

from app.models.assignment import AssignmentStatus
from app.schemas.assignment import AssignmentTransitionEvent


@dataclass(frozen=True)
class AssignmentTransitionResult:
    from_status: AssignmentStatus
    to_status: AssignmentStatus
    event: AssignmentTransitionEvent


class AssignmentStateMachine:
    _transitions: Dict[AssignmentStatus, Dict[AssignmentTransitionEvent, AssignmentStatus]] = {
        AssignmentStatus.DRAFT: {
            AssignmentTransitionEvent.PUBLISH: AssignmentStatus.PUBLISHED,
        },
        AssignmentStatus.PUBLISHED: {
            AssignmentTransitionEvent.REACH_DEADLINE: AssignmentStatus.DEADLINE,
            AssignmentTransitionEvent.ARCHIVE: AssignmentStatus.ARCHIVED,
        },
        AssignmentStatus.DEADLINE: {
            AssignmentTransitionEvent.ARCHIVE: AssignmentStatus.ARCHIVED,
        },
        AssignmentStatus.ARCHIVED: {},
        AssignmentStatus.CLOSED: {
            AssignmentTransitionEvent.ARCHIVE: AssignmentStatus.ARCHIVED,
        },
    }

    def transition(self, from_status: AssignmentStatus, event: AssignmentTransitionEvent) -> AssignmentTransitionResult:
        next_status = self._transitions.get(from_status, {}).get(event)
        if not next_status:
            raise ValueError(f"不允许从状态 {from_status.value} 触发事件 {event.value}")
        return AssignmentTransitionResult(from_status=from_status, to_status=next_status, event=event)
