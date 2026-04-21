from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    student_id: Optional[str] = None
    recent_days: int = Field(default=30, ge=1, le=365)
    assignment_limit: int = Field(default=5, ge=1, le=20)


class AIChatToolCall(BaseModel):
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


class AIChatResponse(BaseModel):
    answer: str
    tool_calls: list[AIChatToolCall] = Field(default_factory=list)


class AIChatStreamEvent(BaseModel):
    event: Literal["status", "thinking_chunk", "tool_call_start", "tool_call_result", "message_chunk", "done", "error"]
    data: dict[str, Any]


class AIChatConversation(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str


class AIChatConversationListResponse(BaseModel):
    total: int
    items: list[AIChatConversation]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class AIChatMessage(BaseModel):
    message_id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    tool_calls: list[AIChatToolCall] = Field(default_factory=list)
    created_at: str


class AIChatMessageListResponse(BaseModel):
    total: int
    items: list[AIChatMessage]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class AIChatConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
