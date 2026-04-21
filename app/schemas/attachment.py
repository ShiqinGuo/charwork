from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AttachmentBase(BaseModel):
    file_url: str
    filename: str
    file_size: int
    mime_type: str


class AttachmentCreate(AttachmentBase):
    owner_type: str
    owner_id: str


class AttachmentResponse(AttachmentBase):
    id: str
    owner_type: str
    owner_id: str
    management_system_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentListResponse(BaseModel):
    items: List[AttachmentResponse]
    total: int
