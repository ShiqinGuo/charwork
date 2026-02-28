from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    sender_id: str
    receiver_id: str
    title: Optional[str] = None
    content: str


class MessageResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    title: Optional[str] = None
    content: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
