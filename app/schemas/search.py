from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel


class SearchHit(BaseModel):
    module: str
    id: str
    score: float
    title: str
    content: str
    target_type: str
    url: str | None = None


class CrossSearchResponse(BaseModel):
    keyword: str
    total: int
    items: list[SearchHit]


class ReindexResponse(BaseModel):
    status: Literal["success", "partial"]
    indexed: int
    failed: int = 0



@dataclass
class PermissionContext:
    """搜索权限上下文，路由层预查询后传入 service。"""
    role: str  # "admin" | "teacher" | "student"
    user_id: str | None = None
    course_ids: list[str] = field(default_factory=list)
    class_ids: list[str] = field(default_factory=list)
    student_user_id: str | None = None
