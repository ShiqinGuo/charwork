from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TargetType(str, Enum):
    ASSIGNMENT = "assignment"
    SUBMISSION = "submission"


class CommentCreate(BaseModel):
    user_id: str
    target_type: TargetType
    target_id: str
    content: str
    parent_id: Optional[str] = None
    reply_to_user_id: Optional[str] = None


class CommentResponse(BaseModel):
    id: str
    user_id: str
    target_type: TargetType
    target_id: str
    parent_id: Optional[str] = None
    root_id: Optional[str] = None
    reply_to_user_id: Optional[str] = None
    content: str
    reply_count: int = 0
    like_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlatCommentItem(BaseModel):
    root: CommentResponse
    replies: list[CommentResponse]


class FlatCommentListResponse(BaseModel):
    total: int
    items: list[FlatCommentItem]


class LikeAction(str, Enum):
    LIKE = "like"
    UNLIKE = "unlike"


class CommentLikeRequest(BaseModel):
    user_id: str
    action: LikeAction = LikeAction.LIKE


class CommentLikeResponse(BaseModel):
    comment_id: str
    user_id: str
    action: LikeAction
    liked: bool
