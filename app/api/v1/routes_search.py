from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_admin, get_current_user

from app.core.database import get_db
from app.core.security import SessionUser
from app.schemas.search import CrossSearchResponse, ReindexResponse
from app.services.cross_search_service import CrossSearchService


router = APIRouter()


@router.get("/", response_model=CrossSearchResponse)
async def cross_search(
    keyword: str = Query(..., min_length=1),
    modules: Optional[list[str]] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: SessionUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理检索。

    参数：
        keyword (str): 字符串结果。
        modules (Optional[list[str]]): 列表结果。
        limit (int): 单次查询的最大返回数量。
        current_user (SessionUser): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await CrossSearchService(db).search(
            keyword=keyword,
            current_user=current_user,
            modules=modules,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"检索服务不可用：{str(e)}")


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_search(
    _current_admin: SessionUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理检索。

    参数：
        _current_admin (SessionUser): SessionUser 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await CrossSearchService(db).reindex()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"重建索引失败：{str(e)}")
