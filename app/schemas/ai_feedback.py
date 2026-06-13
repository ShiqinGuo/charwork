from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AttachmentAIFeedbackPayload(BaseModel):
    attachment_id: str
    char: str
    ocr_text: Optional[str] = None
    stroke_score: Optional[int] = None
    structure_score: Optional[int] = None
    overall_score: Optional[int] = None
    summary: Optional[str] = None


class AttachmentAIFeedbackResponse(BaseModel):
    id: Optional[str] = None
    attachment_id: str
    status: str
    visibility_scope: str
    payload: Optional[AttachmentAIFeedbackPayload] = None
    created_at: datetime
    updated_at: datetime


class AttachmentAIFeedbackListResponse(BaseModel):
    items: list[AttachmentAIFeedbackResponse]


class SubmissionAISummaryPayload(BaseModel):
    submission_id: str
    attachment_count: int
    summary: str
    strengths: list[str] = []
    improvements: list[str] = []
    overall_level: Optional[str] = None


class SubmissionAISummaryResponse(BaseModel):
    id: Optional[str] = None
    status: str
    visibility_scope: str
    payload: Optional[SubmissionAISummaryPayload] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionAISummaryTriggerResponse(BaseModel):
    status: str
    submission_id: str
