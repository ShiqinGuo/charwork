from typing import Optional
from pydantic import BaseModel


class ExportRequest(BaseModel):
    fields: list[str]
    structure: Optional[str] = None
    level: Optional[str] = None
    variant: Optional[str] = None
    search: Optional[str] = None
