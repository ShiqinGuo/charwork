"""
为什么这样做：提交状态迁移集中到显式状态机，避免服务层散落硬编码状态值。
特殊逻辑：学生修改提交属于“重新提交”事件，允许从 submitted 和 graded 回到 submitted。
"""

from dataclasses import dataclass
from typing import Dict

from app.models.submission import SubmissionStatus
from app.schemas.submission import SubmissionTransitionEvent


@dataclass(frozen=True)
class SubmissionTransitionResult:
    from_status: SubmissionStatus
    to_status: SubmissionStatus
    event: SubmissionTransitionEvent


class SubmissionStateMachine:
    _transitions: Dict[SubmissionStatus, Dict[SubmissionTransitionEvent, SubmissionStatus]] = {
        SubmissionStatus.SUBMITTED: {
            SubmissionTransitionEvent.RESUBMIT: SubmissionStatus.SUBMITTED,
            SubmissionTransitionEvent.GRADE: SubmissionStatus.GRADED,
        },
        SubmissionStatus.GRADED: {
            SubmissionTransitionEvent.RESUBMIT: SubmissionStatus.SUBMITTED,
            SubmissionTransitionEvent.GRADE: SubmissionStatus.GRADED,
        },
    }

    def transition(
        self,
        from_status: SubmissionStatus,
        event: SubmissionTransitionEvent,
    ) -> SubmissionTransitionResult:
        """
        功能描述：
            根据当前状态与事件计算提交状态迁移结果。

        参数：
            from_status (SubmissionStatus): 当前提交状态。
            event (SubmissionTransitionEvent): 触发的状态迁移事件。

        返回值：
            SubmissionTransitionResult: 返回迁移结果对象。
        """
        next_status = self._transitions.get(from_status, {}).get(event)
        if not next_status:
            raise ValueError(f"不允许从状态 {from_status.value} 触发事件 {event.value}")
        return SubmissionTransitionResult(
            from_status=from_status,
            to_status=next_status,
            event=event,
        )
