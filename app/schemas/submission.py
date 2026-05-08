from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum
from app.schemas.attachment import AttachmentResponse


class SubmissionStatus(str, Enum):
    SUBMITTED = "submitted"
    GRADED = "graded"


class SubmissionTransitionEvent(str, Enum):
    RESUBMIT = "resubmit"
    GRADE = "grade"


class SubmissionBase(BaseModel):
    content: Optional[str] = None


class SubmissionCreate(SubmissionBase):
    student_id: Optional[str] = None
    attachment_ids: Optional[List[str]] = None


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
    status: SubmissionStatus
    score: Optional[int] = None
    teacher_feedback: Optional[str] = None
    attachments: List[AttachmentResponse] = []
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


class BatchGradeItem(BaseModel):
    submission_id: str = Field(..., description="提交记录ID")
    score: int = Field(..., ge=0, le=100, description="分数 0-100")
    feedback: str | None = Field(None, description="教师评语")


class BatchGradeRequest(BaseModel):
    grades: list[BatchGradeItem] = Field(..., min_length=1, max_length=100, description="批量批改列表，最多100条")


class BatchGradeFailedItem(BaseModel):
    submission_id: str
    error: str


class BatchGradeResponse(BaseModel):
    total: int = Field(..., description="请求总数")
    success: int = Field(..., description="成功数量")
    failed: list[BatchGradeFailedItem] = Field(default_factory=list, description="失败明细")
