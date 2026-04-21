from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CourseStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CourseBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    status: CourseStatus = CourseStatus.ACTIVE
    custom_field_values: dict[str, Any] = Field(default_factory=dict)


class CourseCreate(CourseBase):
    teaching_class_id: str


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CourseStatus] = None
    teaching_class_id: Optional[str] = None
    custom_field_values: Optional[dict[str, Any]] = None


class CourseResponse(CourseBase):
    id: str
    teaching_class_id: str
    teacher_id: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseSummary(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    status: CourseStatus
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class CourseListResponse(BaseModel):
    total: int
    items: list[CourseResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None
