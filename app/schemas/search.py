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
    status: str
    indexed: int
