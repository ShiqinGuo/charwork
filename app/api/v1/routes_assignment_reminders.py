from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher, get_current_user
from app.core.database import get_db
from app.core.management_scope import ManagementScope, get_management_scope
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.assignment_reminder import (
    AssignmentReminderExecutionCreate,
    AssignmentReminderExecutionListResponse,
    AssignmentReminderExecutionResponse,
    AssignmentReminderPlanCreate,
    AssignmentReminderPlanListResponse,
    AssignmentReminderPlanResponse,
)
from app.services.assignment_reminder_service import AssignmentReminderService
from app.services.assignment_service import AssignmentService


router = APIRouter()


async def _ensure_teacher_assignment(
    assignment_id: str,
    management_system_id: str,
    teacher: Teacher,
    db: AsyncSession,
):
    """
    功能描述：
        确保教师作业存在，必要时自动补齐。

    参数：
        assignment_id (str): 作业ID。
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        teacher (Teacher): Teacher 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    existing = await AssignmentService(db).get_assignment(assignment_id, management_system_id)
    if existing and existing.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="仅可维护本人作业的提醒计划")
    if not existing:
        raise HTTPException(status_code=404, detail="作业不存在")


@router.get("/{assignment_id}/reminder-plans", response_model=AssignmentReminderPlanListResponse)
async def list_assignment_reminder_plans(
    assignment_id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询作业提醒plans列表。

    参数：
        assignment_id (str): 作业ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentReminderPlanListResponse: 作业提醒计划列表对象。
    """
    try:
        return await AssignmentReminderService(db).list_plans(assignment_id, scope.management_system_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{assignment_id}/reminder-plans",
    response_model=AssignmentReminderPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment_reminder_plan(
    assignment_id: str,
    body: AssignmentReminderPlanCreate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建作业提醒计划并返回结果。

    参数：
        assignment_id (str): 作业ID。
        body (AssignmentReminderPlanCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentReminderPlanResponse: 作业提醒计划对象。
    """
    await _ensure_teacher_assignment(assignment_id, scope.management_system_id, current_teacher, db)
    try:
        return await AssignmentReminderService(db).create_plan(
            assignment_id,
            scope.management_system_id,
            current_user.id,
            body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{assignment_id}/reminder-plans/sync",
    response_model=AssignmentReminderPlanListResponse,
)
async def sync_assignment_reminder_plans(
    assignment_id: str,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        同步作业提醒plans。

    参数：
        assignment_id (str): 作业ID。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentReminderPlanListResponse: 作业提醒计划列表对象。
    """
    await _ensure_teacher_assignment(assignment_id, scope.management_system_id, current_teacher, db)
    try:
        return await AssignmentReminderService(db).sync_plans_for_assignment(
            assignment_id,
            scope.management_system_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{assignment_id}/reminder-executions", response_model=AssignmentReminderExecutionListResponse)
async def list_assignment_reminder_executions(
    assignment_id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询作业提醒executions列表。

    参数：
        assignment_id (str): 作业ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentReminderExecutionListResponse: 作业提醒执行记录列表对象。
    """
    try:
        return await AssignmentReminderService(db).list_executions(assignment_id, scope.management_system_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{assignment_id}/reminder-executions",
    response_model=AssignmentReminderExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment_reminder_execution(
    assignment_id: str,
    body: AssignmentReminderExecutionCreate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建作业提醒执行记录并返回结果。

    参数：
        assignment_id (str): 作业ID。
        body (AssignmentReminderExecutionCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentReminderExecutionResponse: 作业提醒执行记录对象。
    """
    await _ensure_teacher_assignment(assignment_id, scope.management_system_id, current_teacher, db)
    try:
        return await AssignmentReminderService(db).create_execution(
            assignment_id,
            scope.management_system_id,
            body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{assignment_id}/reminder-executions/execute-due",
    response_model=AssignmentReminderExecutionListResponse,
)
async def execute_due_assignment_reminders(
    assignment_id: str,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        执行due作业提醒。

    参数：
        assignment_id (str): 作业ID。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        AssignmentReminderExecutionListResponse: 作业提醒执行记录列表对象。
    """
    await _ensure_teacher_assignment(assignment_id, scope.management_system_id, current_teacher, db)
    try:
        return await AssignmentReminderService(db).execute_due_plans(
            assignment_id,
            scope.management_system_id,
            current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
