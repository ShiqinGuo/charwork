from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ManagementSystemOwner(BaseModel):
    id: str
    username: str
    role: str
    display_name: Optional[str] = None


class ManagementSystemBase(BaseModel):
    name: str
    description: Optional[str] = None
    system_type: str = "custom"
    config: dict[str, Any] = Field(default_factory=dict)


class ManagementSystemCreate(ManagementSystemBase):
    pass


class ManagementSystemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class ManagementSystemResponse(ManagementSystemBase):
    id: str
    preset_key: Optional[str] = None
    is_default: bool
    owner_user_id: str
    owner: ManagementSystemOwner
    is_owner: bool
    can_edit: bool
    created_at: datetime
    updated_at: datetime


class ManagementSystemListResponse(BaseModel):
    total: int
    items: list[ManagementSystemResponse]
