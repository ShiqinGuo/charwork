from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.services.teacher_service import TeacherService


router = APIRouter()


@router.get("/")
async def list_teachers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await TeacherService(db).list_teachers(skip, limit)


@router.post("/", response_model=TeacherResponse)
async def create_teacher(body: TeacherCreate, db: AsyncSession = Depends(get_db)):
    return await TeacherService(db).create_teacher(body)


@router.get("/{id}", response_model=TeacherResponse)
async def get_teacher(id: str, db: AsyncSession = Depends(get_db)):
    teacher = await TeacherService(db).get_teacher(id)
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")
    return teacher


@router.put("/{id}", response_model=TeacherResponse)
async def update_teacher(id: str, body: TeacherUpdate, db: AsyncSession = Depends(get_db)):
    teacher = await TeacherService(db).update_teacher(id, body)
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")
    return teacher


@router.delete("/{id}")
async def delete_teacher(id: str, db: AsyncSession = Depends(get_db)):
    ok = await TeacherService(db).delete_teacher(id)
    if not ok:
        raise HTTPException(status_code=404, detail="教师不存在")
    return {"status": "success"}
