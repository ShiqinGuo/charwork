from typing import Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum


class StructureType(str, Enum):
    UNKNOWN = '未知结构'
    LEFT_RIGHT = '左右结构'
    UP_DOWN = '上下结构'
    SURROUND = '包围结构'
    SINGLE = '独体结构'
    PIN = '品字结构'
    INTERLACED = '穿插结构'


class VariantType(str, Enum):
    SIMPLIFIED = '简体'
    TRADITIONAL = '繁体'


class LevelType(str, Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'


class HanziBase(BaseModel):
    character: str
    image_path: Optional[str] = None
    stroke_count: Optional[int] = None
    structure: Optional[StructureType] = StructureType.UNKNOWN
    stroke_order: Optional[str] = None
    pinyin: Optional[str] = None
    level: Optional[LevelType] = LevelType.A
    comment: Optional[str] = None
    variant: Optional[VariantType] = VariantType.SIMPLIFIED
    standard_image: Optional[str] = None


class HanziCreate(HanziBase):
    pass


class HanziUpdate(BaseModel):
    character: Optional[str] = None
    image_path: Optional[str] = None
    stroke_count: Optional[int] = None
    structure: Optional[StructureType] = None
    stroke_order: Optional[str] = None
    pinyin: Optional[str] = None
    level: Optional[LevelType] = None
    comment: Optional[str] = None
    variant: Optional[VariantType] = None
    standard_image: Optional[str] = None


class HanziResponse(HanziBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HanziListResponse(BaseModel):
    total: int
    items: list[HanziResponse]
