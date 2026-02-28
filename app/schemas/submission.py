from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum


class SubmissionStatus(str, Enum):
    SUBMITTED = "submitted"
    GRADED = "graded"


class SubmissionBase(BaseModel):
    content: Optional[str] = None
    image_paths: Optional[List[str]] = None


class SubmissionCreate(SubmissionBase):
    student_id: str


class SubmissionGrade(BaseModel):
    score: int
    feedback: Optional[str] = None


class SubmissionResponse(SubmissionBase):
    id: str
    assignment_id: str
    student_id: str
    status: SubmissionStatus
    score: Optional[int] = None
    feedback: Optional[str] = None
    submitted_at: datetime
    graded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
