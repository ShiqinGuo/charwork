from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssignmentReminderPlanStatus(str, Enum):
    PENDING = "pending"
    DISABLED = "disabled"
    CANCELLED = "cancelled"
    EXECUTED = "executed"


class AssignmentReminderExecutionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class AssignmentReminderPlanBase(BaseModel):
    name: str
    remind_at: datetime
    version: int = 1
    sequence_no: int = 1
    lead_minutes: int = 0
    target_filter: str = "pending_students"
    is_enabled: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class AssignmentReminderPlanCreate(AssignmentReminderPlanBase):
    pass


class AssignmentReminderPlanResponse(AssignmentReminderPlanBase):
    id: str
    assignment_id: str
    course_id: Optional[str] = None
    management_system_id: str
    created_by_user_id: str
    status: AssignmentReminderPlanStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentReminderPlanListResponse(BaseModel):
    total: int
    items: list[AssignmentReminderPlanResponse]


class AssignmentReminderExecutionCreate(BaseModel):
    plan_id: str
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    status: AssignmentReminderExecutionStatus = AssignmentReminderExecutionStatus.PENDING
    target_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class AssignmentReminderExecutionResponse(AssignmentReminderExecutionCreate):
    id: str
    assignment_id: str
    management_system_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentReminderExecutionListResponse(BaseModel):
    total: int
    items: list[AssignmentReminderExecutionResponse]
