from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict


class TargetType(str, Enum):
    ASSIGNMENT = "assignment"
    SUBMISSION = "submission"


class CommentCreate(BaseModel):
    user_id: str
    target_type: TargetType
    target_id: str
    content: str


class CommentResponse(BaseModel):
    id: str
    user_id: str
    target_type: TargetType
    target_id: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
