from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.search import CrossSearchResponse, ReindexResponse
from app.services.cross_search_service import CrossSearchService


router = APIRouter()


@router.get("/", response_model=CrossSearchResponse)
async def cross_search(
    keyword: str = Query(..., min_length=1),
    modules: Optional[list[str]] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await CrossSearchService(db).search(keyword=keyword, modules=modules, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"检索服务不可用：{str(e)}")


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_search(db: AsyncSession = Depends(get_db)):
    try:
        return await CrossSearchService(db).reindex()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"重建索引失败：{str(e)}")
