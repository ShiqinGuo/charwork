from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_teacher, get_current_user
from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.repositories.student_repo import StudentRepository
from app.schemas.assignment import (
    AssignmentActionResponse,
    AssignmentDelayRequest,
    AssignmentResponse,
    AssignmentListResponse,
    AssignmentReminderRequest,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentTransitionRequest,
    AssignmentTransitionResponse,
)
from app.services.attachment_service import AttachmentService
from app.services.assignment_service import AssignmentService
from app.utils.pagination import resolve_pagination

router = APIRouter()


def _bad_request_error(exc: ValueError) -> HTTPException:
    """
    功能描述：
        处理请求error。

    参数：
        exc (ValueError): ValueError 类型的数据。

    返回值：
        HTTPException: 返回HTTPException类型的处理结果。
    """
    return HTTPException(status_code=400, detail=str(exc))


def _not_found_error() -> HTTPException:
    """
    功能描述：
        处理founderror。

    参数：
        无。

    返回值：
        HTTPException: 返回HTTPException类型的处理结果。
    """
    return HTTPException(status_code=404, detail="Assignment not found")


def _ensure_assignment_owner(
    assignment: AssignmentResponse | None,
    teacher_id: str,
    error_message: str,
) -> None:
    """
    功能描述：
        确保作业归属存在，必要时自动补齐。

    参数：
        assignment (AssignmentResponse | None): AssignmentResponse | None 类型的数据。
        teacher_id (str): 教师ID。
        error_message (str): 字符串结果。

    返回值：
        None: 无返回值。
    """
    if not assignment:
        return
    # 在服务层状态校验之外再做路由层归属校验，避免跨教师误操作被包装成普通业务失败。
    if assignment.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail=error_message)


async def _resolve_current_student_id(db: AsyncSession, current_user: User) -> Optional[str]:
    """
    功能描述：
        解析当前学生标识。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        current_user (User): 当前登录用户对象。

    返回值：
        Optional[str]: 返回处理结果对象；无可用结果时返回 None。
    """
    if current_user.role != UserRole.STUDENT:
        return None
    # 学生身份下才解析 student_profile，可避免教师查询链路被无关 join 放大。
    student = await StudentRepository(db).get_by_user_id(current_user.id)
    if not student:
        raise HTTPException(status_code=404, detail="学生档案不存在")
    return student.id


@router.get("/", response_model=AssignmentListResponse)
async def list_assignments(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    status: Optional[str] = None,
    teacher_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    功能描述：
        按条件查询作业列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        status (Optional[str]): 状态筛选条件或目标状态。
        teacher_id (Optional[str]): 教师ID。
        course_id (Optional[str]): 课程ID。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentListResponse: 作业列表对象。
    """
    service = AssignmentService(db)
    # 兼容 page/size 与 skip/limit 两套协议后统一归一化，保证后续查询策略始终只消费一套分页参数。
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    current_student_id = await _resolve_current_student_id(db, current_user)
    return await service.list_assignments(
        skip=pagination["skip"],
        limit=pagination["limit"],
        teacher_id=teacher_id,
        status=status,
        course_id=course_id,
        current_student_id=current_student_id,
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/", response_model=AssignmentResponse)
async def create_assignment(
    assignment_in: AssignmentCreate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建作业并返回结果。

    参数：
        assignment_in (AssignmentCreate): 作业输入对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentResponse: 作业对象。
    """
    service = AssignmentService(db)
    try:
        return await service.create_assignment(assignment_in, current_teacher.id)
    except ValueError as exc:
        raise _bad_request_error(exc) from exc


@router.post("/attachments/upload")
async def upload_assignment_attachment(
    file: UploadFile = File(...),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        上传作业附件。

    参数：
        file (UploadFile): 上传文件对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        dict: 返回包含attachment_id的字典。
    """
    try:
        service = AttachmentService(db)
        attachment = await service.upload_attachment(
            file=file,
            owner_type="assignment",
            owner_id="",
        )
        return {"attachment_id": attachment.id}
    except ValueError as exc:
        raise _bad_request_error(exc) from exc


@router.get("/{id}", response_model=AssignmentResponse)
async def get_assignment(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    功能描述：
        按条件获取作业。

    参数：
        id (str): 目标记录ID。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    assignment = await service.get_assignment(id, current_user.role)
    if not assignment:
        raise _not_found_error()
    return assignment


@router.put("/{id}", response_model=AssignmentResponse)
async def update_assignment(
    id: str,
    assignment_in: AssignmentUpdate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        更新作业并返回最新结果。

    参数：
        id (str): 目标记录ID。
        assignment_in (AssignmentUpdate): 作业输入对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    existing = await service.get_assignment(id)
    _ensure_assignment_owner(existing, current_teacher.id, "仅可维护本人发布的作业")
    try:
        assignment = await service.update_assignment(id, assignment_in)
    except ValueError as exc:
        raise _bad_request_error(exc) from exc
    if not assignment:
        raise _not_found_error()
    return assignment


@router.delete("/{id}")
async def delete_assignment(
    id: str,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        删除作业。

    参数：
        id (str): 目标记录ID。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    existing = await service.get_assignment(id)
    _ensure_assignment_owner(existing, current_teacher.id, "仅可删除本人发布的作业")
    success = await service.delete_assignment(id)
    if not success:
        raise _not_found_error()
    return {"status": "success"}


@router.post("/{id}/transitions", response_model=AssignmentTransitionResponse)
async def transition_assignment(
    id: str,
    body: AssignmentTransitionRequest,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        流转作业。

    参数：
        id (str): 目标记录ID。
        body (AssignmentTransitionRequest): 接口请求体对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    existing = await service.get_assignment(id)
    _ensure_assignment_owner(existing, current_teacher.id, "仅可变更本人发布的作业")
    try:
        result = await service.transition_assignment(id, body.event)
    except ValueError as exc:
        raise _bad_request_error(exc) from exc
    if not result:
        raise _not_found_error()
    return result


@router.post("/transitions/reach-deadline")
async def reach_deadline_assignments(
    _current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        触发截止时间作业。

    参数：
        _current_teacher (Teacher): Teacher 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    affected = await service.reach_deadline_assignments()
    return {"status": "success", "affected": affected}


@router.post("/{id}/publish", response_model=AssignmentActionResponse)
async def publish_assignment(
    id: str,
    current_teacher: Teacher = Depends(get_current_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        发布作业。

    参数：
        id (str): 目标记录ID。
        current_teacher (Teacher): 当前登录教师对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    existing = await service.get_assignment(id)
    _ensure_assignment_owner(existing, current_teacher.id, "仅可发布本人作业")
    try:
        result = await service.publish_assignment(id, current_user.id)
    except ValueError as exc:
        raise _bad_request_error(exc) from exc
    if not result:
        raise _not_found_error()
    return result


@router.post("/{id}/delay", response_model=AssignmentActionResponse)
async def delay_assignment(
    id: str,
    body: AssignmentDelayRequest,
    current_teacher: Teacher = Depends(get_current_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        延期处理作业。

    参数：
        id (str): 目标记录ID。
        body (AssignmentDelayRequest): 接口请求体对象。
        current_teacher (Teacher): 当前登录教师对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    existing = await service.get_assignment(id)
    _ensure_assignment_owner(existing, current_teacher.id, "仅可延期本人作业")
    try:
        result = await service.delay_assignment(id, body, current_user.id)
    except ValueError as exc:
        raise _bad_request_error(exc) from exc
    if not result:
        raise _not_found_error()
    return result


@router.post("/{id}/remind", response_model=AssignmentActionResponse)
async def remind_assignment(
    id: str,
    body: AssignmentReminderRequest,
    current_teacher: Teacher = Depends(get_current_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理作业。

    参数：
        id (str): 目标记录ID。
        body (AssignmentReminderRequest): 接口请求体对象。
        current_teacher (Teacher): 当前登录教师对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = AssignmentService(db)
    existing = await service.get_assignment(id)
    _ensure_assignment_owner(existing, current_teacher.id, "仅可提醒本人作业")
    try:
        result = await service.remind_assignment(id, body, current_user.id)
    except ValueError as exc:
        raise _bad_request_error(exc) from exc
    if not result:
        raise _not_found_error()
    return result
