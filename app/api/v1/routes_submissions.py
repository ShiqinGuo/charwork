from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.submission import SubmissionCreate, SubmissionGrade, SubmissionResponse
from app.services.submission_service import SubmissionService


router = APIRouter()


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionResponse)
async def create_submission(assignment_id: str, body: SubmissionCreate, db: AsyncSession = Depends(get_db)):
    return await SubmissionService(db).create_submission(assignment_id, body)


@router.get("/assignments/{assignment_id}/submissions")
async def list_submissions(
    assignment_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await SubmissionService(db).list_submissions_by_assignment(assignment_id, skip, limit)


@router.get("/submissions/{id}", response_model=SubmissionResponse)
async def get_submission(id: str, db: AsyncSession = Depends(get_db)):
    submission = await SubmissionService(db).get_submission(id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return submission


@router.put("/submissions/{id}/grade", response_model=SubmissionResponse)
async def grade_submission(id: str, body: SubmissionGrade, db: AsyncSession = Depends(get_db)):
    submission = await SubmissionService(db).grade_submission(id, body)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return submission
