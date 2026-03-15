from pydantic import BaseModel


class SearchHit(BaseModel):
    module: str
    id: str
    score: float
    title: str
    content: str


class CrossSearchResponse(BaseModel):
    keyword: str
    total: int
    items: list[SearchHit]


class ReindexResponse(BaseModel):
    status: str
    indexed: int
