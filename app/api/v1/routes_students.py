from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher
from app.core.database import get_db
from app.models.teacher import Teacher
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.services.student_service import StudentService
from app.services.student_class_service import StudentClassService


router = APIRouter()


@router.get("/")
async def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """返回当前教师教学班中的学生列表。"""
    return await StudentService(db).list_students_by_teacher(
        current_teacher.id, skip, limit
    )


@router.post("/", response_model=StudentResponse)
async def create_student(
    body: StudentCreate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """创建学生并加入指定的教学班。"""
    teaching_class_repo = TeachingClassRepository(db)
    target_class = await teaching_class_repo.get(body.teaching_class_id)
    if not target_class:
        raise HTTPException(status_code=404, detail="教学班不存在")
    if target_class.teacher_id != current_teacher.id:
        raise HTTPException(status_code=403, detail="仅可向自己的教学班添加学生")

    svc = StudentService(db)
    student = await svc.create_student(body)
    try:
        await StudentClassService(db).join_class(student.id, body.teaching_class_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return student


@router.get("/{id}", response_model=StudentResponse)
async def get_student(
    id: str,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取学生详情（仅限当前教师教学班中的学生）。"""
    svc = StudentService(db)
    if not await svc.is_student_in_teacher_class(id, current_teacher.id):
        raise HTTPException(status_code=404, detail="学生不在您的教学班中")
    student = await svc.get_student(id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.put("/{id}", response_model=StudentResponse)
async def update_student(
    id: str,
    body: StudentUpdate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """更新学生资料（仅限当前教师教学班中的学生）。"""
    svc = StudentService(db)
    if not await svc.is_student_in_teacher_class(id, current_teacher.id):
        raise HTTPException(status_code=404, detail="学生不在您的教学班中")
    student = await svc.update_student(id, body)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.delete("/{id}")
async def remove_student_from_class(
    id: str,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """将学生从当前教师的教学班中移除（解除关联，不删除学生账号）。"""
    ok = await StudentService(db).remove_student_from_class(id, current_teacher.id)
    if not ok:
        raise HTTPException(status_code=404, detail="学生不在您的教学班中")
    return {"status": "success", "detail": "已从教学班中移除"}
