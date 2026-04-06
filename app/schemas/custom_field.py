from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CustomFieldTargetType(str, Enum):
    COURSE = "course"
    ASSIGNMENT = "assignment"
    STUDENT = "student"


class CustomFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    SELECT = "select"
    JSON = "json"


class ManagementSystemCustomFieldBase(BaseModel):
    name: str
    field_key: str
    field_type: CustomFieldType
    target_type: CustomFieldTargetType
    is_required: bool = False
    is_searchable: bool = False
    default_value: Optional[Any] = None
    options: Optional[dict[str, Any]] = None
    validation_rules: Optional[dict[str, Any]] = None
    # visibility_roles 为空表示沿用系统默认可见策略；显式传值时由服务层按角色白名单收敛访问面。
    visibility_roles: Optional[list[str]] = None
    sort_order: int = 0
    is_active: bool = True


class ManagementSystemCustomFieldCreate(ManagementSystemCustomFieldBase):
    pass


class ManagementSystemCustomFieldUpdate(BaseModel):
    name: Optional[str] = None
    field_type: Optional[CustomFieldType] = None
    is_required: Optional[bool] = None
    is_searchable: Optional[bool] = None
    default_value: Optional[Any] = None
    options: Optional[dict[str, Any]] = None
    validation_rules: Optional[dict[str, Any]] = None
    visibility_roles: Optional[list[str]] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ManagementSystemCustomFieldResponse(ManagementSystemCustomFieldBase):
    id: str
    management_system_id: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManagementSystemCustomFieldListResponse(BaseModel):
    total: int
    items: list[ManagementSystemCustomFieldResponse]


class ManagementSystemCustomFieldValueItem(BaseModel):
    field_id: str
    value: Optional[Any] = None


class ManagementSystemCustomFieldValueUpsertRequest(BaseModel):
    # 默认空列表使“清空自定义值”与“部分更新”共用同一提交结构，减少接口分叉。
    values: list[ManagementSystemCustomFieldValueItem] = Field(default_factory=list)


class ManagementSystemCustomFieldValueResponse(BaseModel):
    id: str
    field_id: str
    management_system_id: str
    target_type: CustomFieldTargetType
    target_id: str
    value: Optional[Any] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManagementSystemCustomFieldValueListResponse(BaseModel):
    total: int
    items: list[ManagementSystemCustomFieldValueResponse]


class ManagementSystemCustomFieldSearchItem(BaseModel):
    field_id: str
    field_key: str
    target_type: CustomFieldTargetType
    target_id: str
    value: Optional[Any] = None


class ManagementSystemCustomFieldSearchResponse(BaseModel):
    total: int
    items: list[ManagementSystemCustomFieldSearchItem]
