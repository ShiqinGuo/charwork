from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum


class AssignmentStatus(str, Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    CLOSED = 'closed'


class AssignmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    hanzi_ids: Optional[List[str]] = []
    due_date: Optional[datetime] = None
    status: Optional[AssignmentStatus] = AssignmentStatus.DRAFT


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    hanzi_ids: Optional[List[str]] = None
    due_date: Optional[datetime] = None
    status: Optional[AssignmentStatus] = None


class AssignmentResponse(AssignmentBase):
    id: str
    teacher_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentListResponse(BaseModel):
    total: int
    items: List[AssignmentResponse]
