"""
为什么这样做：状态迁移使用显式映射，保证状态闭环可审计，避免隐式 if/else 跳转。
特殊逻辑：未定义迁移直接抛错作为边界保护，阻止非法事件推进状态。
"""

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
        """
        功能描述：
            流转AssignmentStateMachine。

        参数：
            from_status (AssignmentStatus): 状态信息。
            event (AssignmentTransitionEvent): AssignmentTransitionEvent 类型的数据。

        返回值：
            AssignmentTransitionResult: 返回AssignmentTransitionResult类型的处理结果。
        """
        next_status = self._transitions.get(from_status, {}).get(event)
        if not next_status:
            raise ValueError(f"不允许从状态 {from_status.value} 触发事件 {event.value}")
        return AssignmentTransitionResult(from_status=from_status, to_status=next_status, event=event)
