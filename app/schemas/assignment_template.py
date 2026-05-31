from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class AssignmentTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    character_ids: Optional[List[str]] = None
    course_id: Optional[str] = None
    due_days: Optional[int] = Field(None, ge=1, description="截止天数")


class AssignmentTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    character_ids: Optional[List[str]] = None
    course_id: Optional[str] = None
    due_days: Optional[int] = Field(None, ge=1)


class AssignmentTemplateResponse(BaseModel):
    id: str
    teacher_id: str
    name: str
    description: Optional[str] = None
    character_ids: Optional[List[str]] = None
    course_id: Optional[str] = None
    due_days: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssignmentTemplateListResponse(BaseModel):
    total: int
    items: List[AssignmentTemplateResponse]
