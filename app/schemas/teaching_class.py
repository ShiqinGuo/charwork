from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.course import CourseSummary


class TeachingClassStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TeachingClassMemberStatus(str, Enum):
    ACTIVE = "active"
    LEFT = "left"


class TeachingClassJoinTokenStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    USED_UP = "used_up"


class TeachingClassBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: TeachingClassStatus = TeachingClassStatus.ACTIVE


class TeachingClassCreate(TeachingClassBase):
    pass


class TeachingClassResponse(TeachingClassBase):
    id: str
    management_system_id: str
    teacher_id: str
    is_default: bool
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeachingClassListResponse(BaseModel):
    total: int
    items: list[TeachingClassResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class TeachingClassMemberResponse(BaseModel):
    id: str
    teaching_class_id: str
    student_id: str
    student_name: Optional[str] = None
    joined_by_token_id: Optional[str] = None
    status: TeachingClassMemberStatus
    joined_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeachingClassMemberListResponse(BaseModel):
    total: int
    items: list[TeachingClassMemberResponse]


class TeachingClassJoinTokenCreate(BaseModel):
    title: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None


class TeachingClassJoinTokenResponse(BaseModel):
    id: str
    teaching_class_id: str
    token: str
    title: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    used_count: int
    status: TeachingClassJoinTokenStatus
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeachingClassJoinPreviewResponse(BaseModel):
    token_status: TeachingClassJoinTokenStatus
    can_join: bool
    already_joined: bool
    expires_at: Optional[datetime] = None
    teaching_class: TeachingClassResponse
    courses: list[CourseSummary]
    member: Optional[TeachingClassMemberResponse] = None


class TeachingClassJoinConfirmResponse(BaseModel):
    joined: bool
    teaching_class: TeachingClassResponse
    courses: list[CourseSummary]
    member: TeachingClassMemberResponse
