from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.hanzi import HanziResponse, HanziListResponse, HanziCreate, HanziUpdate
from app.services.hanzi_service import HanziService

router = APIRouter()


@router.get("/", response_model=HanziListResponse)
async def list_hanzi(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    structure: Optional[str] = None,
    level: Optional[str] = None,
    variant: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    service = HanziService(db)
    return await service.list_hanzi(skip, limit, structure, level, variant, search)


@router.post("/", response_model=HanziResponse)
async def create_hanzi(
    hanzi_in: HanziCreate,
    db: AsyncSession = Depends(get_db)
):
    service = HanziService(db)
    return await service.create_hanzi(hanzi_in)


@router.get("/strokes/{character}")
async def get_strokes(character: str, db: AsyncSession = Depends(get_db)):
    service = HanziService(db)
    return service.get_strokes(character)


@router.get("/stroke-search", response_model=HanziListResponse)
async def stroke_search(
    pattern: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = HanziService(db)
    return await service.search_by_stroke_order(pattern, skip, limit)


@router.get("/{id}", response_model=HanziResponse)
async def get_hanzi(
    id: str,
    db: AsyncSession = Depends(get_db)
):
    service = HanziService(db)
    hanzi = await service.get_hanzi(id)
    if not hanzi:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return hanzi


@router.put("/{id}", response_model=HanziResponse)
async def update_hanzi(
    id: str,
    hanzi_in: HanziUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = HanziService(db)
    hanzi = await service.update_hanzi(id, hanzi_in)
    if not hanzi:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return hanzi


@router.delete("/{id}")
async def delete_hanzi(
    id: str,
    db: AsyncSession = Depends(get_db)
):
    service = HanziService(db)
    success = await service.delete_hanzi(id)
    if not success:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return {"status": "success"}
