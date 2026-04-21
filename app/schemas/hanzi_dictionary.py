from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.schemas.hanzi import HanziCreate, HanziResponse


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
    hanzi_ids: list[str] = Field(default_factory=list)


class HanziDatasetAppendItemsRequest(BaseModel):
    hanzi_ids: list[str] = Field(default_factory=list)


class HanziDatasetCreateHanziRequest(BaseModel):
    hanzi: HanziCreate


class HanziDatasetResponse(BaseModel):
    id: str
    name: str
    level: Optional[str] = None
    batch_no: Optional[str] = None
    created_by_user_id: str
    hanzi_count: int = 0
    created_at: datetime
    updated_at: datetime


class HanziDatasetDetailResponse(HanziDatasetResponse):
    pass


class HanziDatasetItemsListResponse(BaseModel):
    total: int
    items: list[HanziResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class HanziDatasetAppendItemsResponse(BaseModel):
    dataset: HanziDatasetResponse
    appended_count: int
    total_items: int


class HanziDatasetCreateHanziResponse(BaseModel):
    dataset: HanziDatasetResponse
    hanzi: HanziResponse


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
