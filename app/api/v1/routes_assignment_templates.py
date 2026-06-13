from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher
from app.core.database import get_db
from app.models.teacher import Teacher
from app.schemas.assignment_template import (
    AssignmentTemplateCreate,
    AssignmentTemplateUpdate,
    AssignmentTemplateListResponse,
    AssignmentTemplateResponse,
)
from app.services.assignment_template_service import AssignmentTemplateService

router = APIRouter()


@router.get("/", response_model=AssignmentTemplateListResponse)
async def list_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await AssignmentTemplateService(db).list_templates(teacher.id, skip, limit)


@router.post("/", response_model=AssignmentTemplateResponse)
async def create_template(
    body: AssignmentTemplateCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await AssignmentTemplateService(db).create_template(teacher.id, body)


@router.put("/{id}", response_model=AssignmentTemplateResponse)
async def update_template(
    id: str,
    body: AssignmentTemplateUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await AssignmentTemplateService(db).update_template(id, body)
    if not result:
        raise HTTPException(status_code=404, detail="模板不存在")
    return result


@router.delete("/{id}")
async def delete_template(
    id: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    deleted = await AssignmentTemplateService(db).delete_template(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"status": "deleted"}
