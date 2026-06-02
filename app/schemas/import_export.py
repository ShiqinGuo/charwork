from typing import Optional
from pydantic import BaseModel


class ExportRequest(BaseModel):
    fields: list[str]
    character: Optional[str] = None
    pinyin: Optional[str] = None
    stroke_count: Optional[int] = None
    stroke_pattern: Optional[str] = None
    dataset_id: Optional[str] = None
    source: Optional[str] = None
    structure: Optional[str] = None
    level: Optional[str] = None
    variant: Optional[str] = None
    search: Optional[str] = None


class DatasetExcelExportRequest(BaseModel):
    hanzi_ids: Optional[list[str]] = None
    character: Optional[str] = None
    pinyin: Optional[str] = None
    stroke_pattern: Optional[str] = None
    # "html+csv" = 默认，导出 index.html + data.csv；"csv" = 仅 CSV
    format: str = "html+csv"
