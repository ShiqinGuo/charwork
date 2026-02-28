from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.assignment import AssignmentResponse, AssignmentListResponse, AssignmentCreate, AssignmentUpdate
from app.services.assignment_service import AssignmentService

router = APIRouter()


# 获取当前教师编号（临时方案：从请求头读取；后续可替换为令牌鉴权）
async def get_current_teacher_id(x_teacher_id: Optional[str] = Header(None)) -> str:
    if not x_teacher_id:
        return "teacher_001"
    return x_teacher_id


@router.get("/", response_model=AssignmentListResponse)
async def list_assignments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    teacher_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    return await service.list_assignments(skip, limit, teacher_id, status)


@router.post("/", response_model=AssignmentResponse)
async def create_assignment(
    assignment_in: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_teacher_id: str = Depends(get_current_teacher_id)
):
    service = AssignmentService(db)
    return await service.create_assignment(assignment_in, current_teacher_id)


@router.get("/{id}", response_model=AssignmentResponse)
async def get_assignment(
    id: str,
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    assignment = await service.get_assignment(id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.put("/{id}", response_model=AssignmentResponse)
async def update_assignment(
    id: str,
    assignment_in: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_teacher_id: str = Depends(get_current_teacher_id)
):
    service = AssignmentService(db)
    assignment = await service.update_assignment(id, assignment_in)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.delete("/{id}")
async def delete_assignment(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_teacher_id: str = Depends(get_current_teacher_id)
):
    service = AssignmentService(db)
    success = await service.delete_assignment(id)
    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"status": "success"}
