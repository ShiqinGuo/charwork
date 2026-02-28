from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate
from app.services.student_service import StudentService


router = APIRouter()


@router.get("/")
async def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await StudentService(db).list_students(skip, limit)


@router.post("/", response_model=StudentResponse)
async def create_student(body: StudentCreate, db: AsyncSession = Depends(get_db)):
    return await StudentService(db).create_student(body)


@router.get("/{id}", response_model=StudentResponse)
async def get_student(id: str, db: AsyncSession = Depends(get_db)):
    student = await StudentService(db).get_student(id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.put("/{id}", response_model=StudentResponse)
async def update_student(id: str, body: StudentUpdate, db: AsyncSession = Depends(get_db)):
    student = await StudentService(db).update_student(id, body)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.delete("/{id}")
async def delete_student(id: str, db: AsyncSession = Depends(get_db)):
    ok = await StudentService(db).delete_student(id)
    if not ok:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {"status": "success"}
