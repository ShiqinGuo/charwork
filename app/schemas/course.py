from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CourseStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CourseBase(BaseModel):
    name: str
    code: str | None = None
    description: str | None = None
    status: CourseStatus = CourseStatus.ACTIVE
    custom_field_values: dict[str, Any] = Field(default_factory=dict)


class CourseCreate(CourseBase):
    teaching_class_ids: list[str] = []


class CourseUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    status: CourseStatus | None = None
    teaching_class_ids: list[str] | None = None
    custom_field_values: dict[str, Any] | None = None


class CourseResponse(CourseBase):
    id: str
    teaching_class_ids: list[str] = []
    teacher_id: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseSummary(BaseModel):
    id: str
    name: str
    code: str | None = None
    status: CourseStatus
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class CourseListResponse(BaseModel):
    total: int
    items: list[CourseResponse]
    page: int | None = None
    size: int | None = None
    skip: int | None = None
    limit: int | None = None
    has_more: bool | None = None
