from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HanziDictionaryInitRequest(BaseModel):
    force: bool = False


class HanziDictionaryInitResponse(BaseModel):
    total: int
    created: int
    updated: int


class HanziDictionaryResponse(BaseModel):
    id: str
    character: str
    stroke_count: Optional[int] = None
    stroke_pattern: Optional[str] = None
    stroke_units: list[str] = Field(default_factory=list)
    pinyin: Optional[str] = None
    source: str
    created_at: datetime
    updated_at: datetime


class HanziDatasetCreate(BaseModel):
    name: str
    level: Optional[str] = None
    batch_no: Optional[str] = None
    dictionary_ids: list[str] = Field(default_factory=list)


class HanziDatasetResponse(BaseModel):
    id: str
    management_system_id: str
    name: str
    level: Optional[str] = None
    batch_no: Optional[str] = None
    created_by_user_id: str
    dictionary_count: int = 0
    created_at: datetime
    updated_at: datetime


class HanziDatasetListResponse(BaseModel):
    total: int
    items: list[HanziDatasetResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class HanziDictionaryListResponse(BaseModel):
    total: int
    items: list[HanziDictionaryResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None
