from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ManagementSystemFieldDefinition(BaseModel):
    field_key: str
    name: str
    field_type: Literal["text", "number", "boolean", "date", "select", "json", "file"] = "text"
    is_required: bool = False
    is_searchable: bool = False
    enabled: bool = True
    options: list[str] = Field(default_factory=list)
    locked: bool = False


class ManagementSystemListConfig(BaseModel):
    visible_field_keys: list[str] = Field(default_factory=list)
    default_sort_field: str = "updated_at"
    default_sort_direction: Literal["asc", "desc"] = "desc"


class ManagementSystemImportExportConfig(BaseModel):
    allow_import: bool = True
    allow_export: bool = True


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


class ManagementSystemRecordBase(BaseModel):
    title: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)
    remark: Optional[str] = None


class ManagementSystemRecordCreate(ManagementSystemRecordBase):
    pass


class ManagementSystemRecordUpdate(BaseModel):
    title: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    remark: Optional[str] = None


class ManagementSystemRecordResponse(ManagementSystemRecordBase):
    id: str
    management_system_id: str
    owner_user_id: str
    created_at: datetime
    updated_at: datetime


class ManagementSystemRecordListResponse(BaseModel):
    total: int
    items: list[ManagementSystemRecordResponse]


class ManagementSystemImportTemplateResponse(BaseModel):
    file_name: str
    file_url: str


class ManagementSystemImportError(BaseModel):
    row: int
    field_key: Optional[str] = None
    message: str


class ManagementSystemImportResponse(BaseModel):
    success_count: int
    failure_count: int
    errors: list[ManagementSystemImportError]


class ManagementSystemExportRequest(BaseModel):
    field_keys: list[str] = Field(default_factory=list)


class ManagementSystemExportResponse(BaseModel):
    file_name: str
    file_url: str
    total: int
