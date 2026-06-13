from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    dictionary_id: Optional[str] = None
    character: str
    image_path: Optional[str] = None
    stroke_count: Optional[int] = None
    structure: Optional[StructureType] = StructureType.UNKNOWN
    stroke_order: Optional[str] = None
    stroke_pattern: Optional[str] = None
    pinyin: Optional[str] = None
    source: Optional[str] = None
    level: Optional[LevelType] = LevelType.A
    comment: Optional[str] = None
    variant: Optional[VariantType] = VariantType.SIMPLIFIED
    standard_image: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_character(cls, data):
        """
        功能描述：
            处理character。

        参数：
            data (Any): 数据。

        返回值：
            None: 无返回值。
        """
        if isinstance(data, dict):
            copied = dict(data)
            if not copied.get("character") and copied.get("char"):
                copied["character"] = copied["char"]
            return copied
        return data


class HanziCreate(HanziBase):
    pass


class HanziUpdate(BaseModel):
    dictionary_id: Optional[str] = None
    character: Optional[str] = None
    char: Optional[str] = None
    image_path: Optional[str] = None
    stroke_count: Optional[int] = None
    structure: Optional[StructureType] = None
    stroke_order: Optional[str] = None
    stroke_pattern: Optional[str] = None
    pinyin: Optional[str] = None
    source: Optional[str] = None
    level: Optional[LevelType] = None
    comment: Optional[str] = None
    variant: Optional[VariantType] = None
    standard_image: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_character(cls, data):
        """
        功能描述：
            处理character。

        参数：
            data (Any): 数据。

        返回值：
            None: 无返回值。
        """
        if isinstance(data, dict):
            copied = dict(data)
            if not copied.get("character") and copied.get("char"):
                copied["character"] = copied["char"]
            return copied
        return data


class HanziResponse(HanziBase):
    id: str
    char: str
    stroke_units: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HanziListResponse(BaseModel):
    total: int
    items: list[HanziResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None


class OCRDictionaryCandidate(BaseModel):
    id: str
    character: str
    pinyin: Optional[str] = None
    stroke_count: Optional[int] = None
    stroke_pattern: Optional[str] = None
    source: Optional[str] = None


class HanziOCRPrefillResponse(BaseModel):
    recognized_text: str
    draft: HanziCreate
    candidates: list[OCRDictionaryCandidate] = Field(default_factory=list)


class HanziOCRBatchPrefillItem(BaseModel):
    file_name: str
    recognized_text: str
    draft: HanziCreate
    candidates: list[OCRDictionaryCandidate] = Field(default_factory=list)


class HanziOCRBatchPrefillResponse(BaseModel):
    total: int
    items: list[HanziOCRBatchPrefillItem]
