from typing import Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from enum import Enum


class AssignmentStatus(str, Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    DEADLINE = 'deadline'
    ARCHIVED = 'archived'
    CLOSED = 'closed'


class AssignmentAttachment(BaseModel):
    name: str
    url: Optional[str] = None
    file_key: Optional[str] = None
    media_type: Optional[str] = None
    size: Optional[int] = None


class AssignmentInstructionStep(BaseModel):
    title: Optional[str] = None
    content: str
    sort_order: int = 0
    attachments: List[AssignmentAttachment] = Field(default_factory=list)


class AssignmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    character_ids: List[str] = Field(default_factory=list)
    course_id: Optional[str] = None
    instruction_steps: List[AssignmentInstructionStep] = Field(default_factory=list)
    attachments: List[AssignmentAttachment] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    status: Optional[AssignmentStatus] = AssignmentStatus.DRAFT
    management_system_id: Optional[str] = None
    custom_field_values: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_character_ids(cls, data):
        """
        功能描述：
            处理character标识列表。

        参数：
            data (Any): 数据。

        返回值：
            None: 无返回值。
        """
        if isinstance(data, dict):
            copied = dict(data)
            # 兼容历史 hanzi_ids 与新字段 character_ids 双写请求，确保不同客户端版本走同一数据通道。
            if copied.get("character_ids") is None and copied.get("hanzi_ids") is not None:
                copied["character_ids"] = copied["hanzi_ids"]
            if copied.get("hanzi_ids") is None and copied.get("character_ids") is not None:
                copied["hanzi_ids"] = copied["character_ids"]
            return copied
        return data


class AssignmentCreate(AssignmentBase):
    course_id: str


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    character_ids: Optional[List[str]] = None
    hanzi_ids: Optional[List[str]] = None
    course_id: Optional[str] = None
    instruction_steps: Optional[List[AssignmentInstructionStep]] = None
    attachments: Optional[List[AssignmentAttachment]] = None
    due_date: Optional[datetime] = None
    status: Optional[AssignmentStatus] = None
    management_system_id: Optional[str] = None
    custom_field_values: Optional[dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_character_ids(cls, data):
        """
        功能描述：
            处理character标识列表。

        参数：
            data (Any): 数据。

        返回值：
            None: 无返回值。
        """
        if isinstance(data, dict):
            copied = dict(data)
            # 更新场景保持同样兼容策略，避免“创建可用、更新失败”的接口行为分叉。
            if copied.get("character_ids") is None and copied.get("hanzi_ids") is not None:
                copied["character_ids"] = copied["hanzi_ids"]
            if copied.get("hanzi_ids") is None and copied.get("character_ids") is not None:
                copied["hanzi_ids"] = copied["character_ids"]
            return copied
        return data


class AssignmentResponse(AssignmentBase):
    id: str
    teacher_id: str
    course_id: str
    hanzi_ids: List[str] = Field(default_factory=list)
    course_name: Optional[str] = None
    teaching_class_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentListResponse(BaseModel):
    total: int
    items: List[AssignmentResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class AssignmentTransitionEvent(str, Enum):
    PUBLISH = "publish"
    REACH_DEADLINE = "reach_deadline"
    ARCHIVE = "archive"


class AssignmentTransitionRequest(BaseModel):
    event: AssignmentTransitionEvent


class AssignmentTransitionResponse(BaseModel):
    assignment: AssignmentResponse
    from_status: AssignmentStatus
    to_status: AssignmentStatus
    event: AssignmentTransitionEvent


class AssignmentDelayRequest(BaseModel):
    due_date: datetime
    reason: Optional[str] = None
    notify_students: bool = True


class AssignmentReminderRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class AssignmentActionResponse(BaseModel):
    assignment: AssignmentResponse
    action: str
    affected_students: int
