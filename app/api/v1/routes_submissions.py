from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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
    SubmissionResponse, TeacherFeedbackUpdate, AIFeedbackResponse,
)
from app.services.submission_service import SubmissionService
from app.services.attachment_service import AttachmentService
from app.utils.pagination import resolve_pagination


router = APIRouter()


async def _get_current_student_id_or_404(
    current_user: User,
    db: AsyncSession,
) -> str:
    """
    功能描述：
        获取当前登录学生的 student_id，不存在时抛出 404。

    参数：
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话。

    返回值：
        str: 返回学生ID。
    """
    student = await StudentRepository(db).get_by_user_id(current_user.id)
    if not student:
        raise HTTPException(status_code=404, detail="学生档案不存在")
    return student.id


@router.get("/teacher/submissions", response_model=SubmissionListResponse)
async def list_teacher_submissions(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    status: Optional[str] = Query(None, description="提交状态筛选: submitted, graded"),
    assignment_id: Optional[str] = Query(None, description="作业ID筛选"),
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        获取教师所有提交记录列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        status (Optional[str]): 提交状态筛选。
        assignment_id (Optional[str]): 作业ID筛选。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        SubmissionListResponse: 返回提交列表。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await SubmissionService(db).list_submissions_by_teacher(
        teacher_id=current_teacher.id,
        management_system_id=scope.management_system_id,
        status=status,
        assignment_id=assignment_id,
        skip=pagination["skip"],
        limit=pagination["limit"],
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionResponse)
async def create_submission(
    assignment_id: str,
    content: Optional[str] = Form(None),
    student_id: Optional[str] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
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
    service = SubmissionService(db)
    assignment = await AssignmentRepository(db).get(assignment_id, scope.management_system_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    body = SubmissionCreate(
        content=content.strip() if content and content.strip() else None,
        attachment_ids=[],
        student_id=student_id,
    )
    if current_user.role == UserRole.STUDENT:
        current_student_id = await _get_current_student_id_or_404(current_user, db)
        accessible_course_ids = await CourseRepository(db).list_ids_for_student(
            current_student_id,
            scope.management_system_id,
        )
        if assignment.course_id not in accessible_course_ids:
            raise HTTPException(status_code=403, detail="仅可提交所属课程作业")
        body.student_id = current_student_id
    if current_user.role != UserRole.STUDENT and not body.student_id:
        raise HTTPException(status_code=400, detail="缺少 student_id")
    existing_submission = await service.get_latest_submission_for_student(
        assignment_id=assignment_id,
        student_id=body.student_id,
        management_system_id=scope.management_system_id,
    )
    if existing_submission:
        raise HTTPException(status_code=409, detail="当前作业已提交，请改用修改接口")
    try:
        body.attachment_ids = await service.upload_submission_images(files or [], scope.management_system_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not body.content and not body.attachment_ids:
        raise HTTPException(status_code=400, detail="提交内容和图片不能同时为空")
    return await service.create_submission(assignment_id, body, scope.management_system_id)


@router.put("/submissions/{id}", response_model=SubmissionResponse)
async def update_submission(
    id: str,
    content: Optional[str] = Form(None),
    retained_attachment_ids: Optional[list[str]] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    scope: ManagementScope = Depends(get_management_scope),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        学生修改自己的提交记录，支持删除已上传附件并追加新图片。

    参数：
        id (str): 提交记录ID。
        content (Optional[str]): 本次提交说明。
        retained_attachment_ids (Optional[list[str]]): 保留的附件ID列表。
        files (Optional[list[UploadFile]]): 本次新增的图片文件列表。
        scope (ManagementScope): 管理系统作用域对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话。

    返回值：
        SubmissionResponse: 返回更新后的提交记录。
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="仅学生可修改自己的提交")
    student_id = await _get_current_student_id_or_404(current_user, db)
    submission_service = SubmissionService(db)
    submission = await submission_service.get_submission(id, scope.management_system_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    if submission.student_id != student_id:
        raise HTTPException(status_code=403, detail="仅可修改自己的提交")
    try:
        uploaded_attachment_ids = await submission_service.upload_submission_images(
            files or [],
            scope.management_system_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 合并保留的和新上传的附件ID
    attachment_ids = list(set((retained_attachment_ids or []) + uploaded_attachment_ids))

    body = SubmissionCreate(
        content=content.strip() if content and content.strip() else None,
        attachment_ids=attachment_ids,
        student_id=student_id,
    )
    if not body.content and not body.attachment_ids:
        raise HTTPException(status_code=400, detail="提交内容和图片不能同时为空")
    updated_submission = await submission_service.update_submission(id, body, scope.management_system_id)
    if not updated_submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return updated_submission


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
        student_id = await _get_current_student_id_or_404(current_user, db)
        assignment = await AssignmentRepository(db).get(assignment_id, scope.management_system_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="作业不存在")
        accessible_course_ids = await CourseRepository(db).list_ids_for_student(
            student_id,
            scope.management_system_id,
        )
        if assignment.course_id not in accessible_course_ids:
            raise HTTPException(status_code=403, detail="仅可查看所属课程提交记录")
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


@router.get("/submissions/{id}/ai-feedback", response_model=AIFeedbackResponse)
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


@router.post("/{assignment_id}/upload-images", response_model=dict)
async def upload_submission_images(
    assignment_id: str,
    files: list[UploadFile] = File(...),
    management_system_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        上传作业图片并返回附件ID列表。

    参数：
        assignment_id (str): 作业ID。
        files (list[UploadFile]): 上传的图片文件列表。
        management_system_id (Optional[str]): 管理系统ID。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        dict: 返回包含 attachment_ids 列表的字典。
    """
    service = SubmissionService(db)
    try:
        attachment_ids = await service.upload_submission_images(
            files=files,
            management_system_id=management_system_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"attachment_ids": attachment_ids}
