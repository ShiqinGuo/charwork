from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher, get_current_user
from app.core.database import get_db
from app.core.management_scope import ManagementScope, get_management_scope
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.repositories.assignment_repo import AssignmentRepository
from app.repositories.course_repo import CourseRepository
from app.repositories.student_repo import StudentRepository
from app.schemas.submission import (
    SubmissionCreate, SubmissionGrade, SubmissionListResponse,
    SubmissionResponse, TeacherFeedbackUpdate,
)
from app.services.submission_service import SubmissionService
from app.utils.pagination import resolve_pagination


router = APIRouter()


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionResponse)
async def create_submission(
    assignment_id: str,
    body: SubmissionCreate,
    scope: ManagementScope = Depends(get_management_scope),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建提交记录并返回结果。

    参数：
        assignment_id (str): 作业ID。
        body (SubmissionCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    assignment = await AssignmentRepository(db).get(assignment_id, scope.management_system_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    student = await StudentRepository(db).get_by_user_id(current_user.id)
    if current_user.role == UserRole.STUDENT:
        if not student:
            raise HTTPException(status_code=404, detail="学生档案不存在")
        accessible_course_ids = await CourseRepository(db).list_ids_for_student(student.id, scope.management_system_id)
        if assignment.course_id not in accessible_course_ids:
            raise HTTPException(status_code=403, detail="仅可提交所属课程作业")
        body.student_id = student.id
    if current_user.role != UserRole.STUDENT and not body.student_id:
        raise HTTPException(status_code=400, detail="缺少 student_id")
    return await SubmissionService(db).create_submission(assignment_id, body, scope.management_system_id)


@router.get("/assignments/{assignment_id}/submissions", response_model=SubmissionListResponse)
async def list_submissions(
    assignment_id: str,
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    scope: ManagementScope = Depends(get_management_scope),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询提交记录列表。

    参数：
        assignment_id (str): 作业ID。
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        scope (ManagementScope): 管理系统作用域对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    student_id = None
    if current_user.role == UserRole.STUDENT:
        student = await StudentRepository(db).get_by_user_id(current_user.id)
        if not student:
            raise HTTPException(status_code=404, detail="学生档案不存在")
        assignment = await AssignmentRepository(db).get(assignment_id, scope.management_system_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="作业不存在")
        accessible_course_ids = await CourseRepository(db).list_ids_for_student(student.id, scope.management_system_id)
        if assignment.course_id not in accessible_course_ids:
            raise HTTPException(status_code=403, detail="仅可查看所属课程提交记录")
        student_id = student.id
    return await SubmissionService(db).list_submissions_by_assignment(
        assignment_id=assignment_id,
        management_system_id=scope.management_system_id,
        student_id=student_id,
        skip=pagination["skip"],
        limit=pagination["limit"],
        page=pagination["page"],
        size=pagination["size"],
    )


@router.get("/submissions/{id}", response_model=SubmissionResponse)
async def get_submission(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取提交记录。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    submission = await SubmissionService(db).get_submission(id, scope.management_system_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return submission


@router.put("/submissions/{id}/grade", response_model=SubmissionResponse)
async def grade_submission(
    id: str,
    body: SubmissionGrade,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理提交记录。

    参数：
        id (str): 目标记录ID。
        body (SubmissionGrade): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    submission = await SubmissionService(db).grade_submission(
        id,
        body,
        scope.management_system_id,
        current_teacher.user_id,
    )
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return submission


@router.get("/submissions/{id}/ai-feedback")
async def get_ai_feedback(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        获取提交记录的 AI 评语，前端可轮询 status 字段判断生成状态。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        dict: 返回 ai_feedback 字典。
    """
    result = await SubmissionService(db).get_ai_feedback(id, scope.management_system_id)
    if result is None:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return result


@router.post("/submissions/{id}/teacher-feedback", response_model=SubmissionResponse)
async def save_teacher_feedback(
    id: str,
    body: TeacherFeedbackUpdate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        保存教师独立评语，不覆盖 AI 评语。

    参数：
        id (str): 目标记录ID。
        body (TeacherFeedbackUpdate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        SubmissionResponse: 返回更新后的结果对象。
    """
    submission = await SubmissionService(db).save_teacher_feedback(
        id=id,
        teacher_feedback=body.teacher_feedback,
        score=body.score,
        management_system_id=scope.management_system_id,
    )
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return submission
