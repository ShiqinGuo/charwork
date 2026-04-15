from typing import Optional, List, Any
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
    student_id: Optional[str] = None


class SubmissionGrade(BaseModel):
    score: int
    # feedback 参数名保留，语义对应 teacher_feedback 列
    feedback: Optional[str] = None


class TeacherFeedbackUpdate(BaseModel):
    teacher_feedback: Optional[str] = None
    score: int


class SubmissionResponse(SubmissionBase):
    id: str
    assignment_id: str
    student_id: str
    management_system_id: Optional[str] = None
    status: SubmissionStatus
    score: Optional[int] = None
    teacher_feedback: Optional[str] = None
    ai_feedback: Optional[Any] = None
    submitted_at: datetime
    graded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionListResponse(BaseModel):
    total: int
    items: List[SubmissionResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class AIFeedbackItem(BaseModel):
    image_index: int
    char: str
    stroke_score: Optional[int] = None
    structure_score: Optional[int] = None
    overall_score: Optional[int] = None
    summary: Optional[str] = None


class AIFeedbackResponse(BaseModel):
    status: str
    generated_at: Optional[str] = None
    items: List[AIFeedbackItem] = []
