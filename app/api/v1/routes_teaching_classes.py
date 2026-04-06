from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_student, get_current_teacher, get_current_user
from app.core.database import get_db
from app.core.management_scope import ManagementScope, get_management_scope
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teaching_class import (
    TeachingClassCreate,
    TeachingClassJoinConfirmResponse,
    TeachingClassJoinPreviewResponse,
    TeachingClassJoinTokenCreate,
    TeachingClassJoinTokenResponse,
    TeachingClassListResponse,
    TeachingClassMemberListResponse,
    TeachingClassResponse,
)
from app.services.teaching_class_service import TeachingClassService
from app.utils.pagination import resolve_pagination


router = APIRouter()


@router.get("/", response_model=TeachingClassListResponse)
async def list_teaching_classes(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    teacher_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询教学班级列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        teacher_id (Optional[str]): 教师ID。
        status_filter (Optional[str]): 状态信息。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await TeachingClassService(db).list_teaching_classes(
        skip=pagination["skip"],
        limit=pagination["limit"],
        management_system_id=scope.management_system_id,
        teacher_id=teacher_id,
        status=status_filter,
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/", response_model=TeachingClassResponse, status_code=status.HTTP_201_CREATED)
async def create_teaching_class(
    body: TeachingClassCreate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建教学班级并返回结果。

    参数：
        body (TeachingClassCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await TeachingClassService(db).create_teaching_class(body, current_teacher.id, scope.management_system_id)


@router.get("/{id}", response_model=TeachingClassResponse)
async def get_teaching_class(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取教学班级。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    item = await TeachingClassService(db).get_teaching_class(id, scope.management_system_id)
    if not item:
        raise HTTPException(status_code=404, detail="教学班级不存在")
    return item


@router.get("/{id}/members", response_model=TeachingClassMemberListResponse)
async def list_teaching_class_members(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询教学班级members列表。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await TeachingClassService(db).list_members(id, scope.management_system_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{id}/join-tokens", response_model=TeachingClassJoinTokenResponse, status_code=status.HTTP_201_CREATED)
async def create_teaching_class_join_token(
    id: str,
    body: TeachingClassJoinTokenCreate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建教学班级加入令牌并返回结果。

    参数：
        id (str): 目标记录ID。
        body (TeachingClassJoinTokenCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await TeachingClassService(db).create_join_token(
            id,
            scope.management_system_id,
            current_teacher.id,
            body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/join-tokens/{token}/preview", response_model=TeachingClassJoinPreviewResponse)
async def preview_join_teaching_class(
    token: str,
    current_user: User = Depends(get_current_user),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理加入教学班级。

    参数：
        token (str): 令牌字符串。
        current_user (User): 当前登录用户对象。
        current_student (Student): 当前学生。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await TeachingClassService(db).preview_join(token, current_user, current_student.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/join-tokens/{token}/confirm", response_model=TeachingClassJoinConfirmResponse)
async def confirm_join_teaching_class(
    token: str,
    current_user: User = Depends(get_current_user),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        确认加入教学班级。

    参数：
        token (str): 令牌字符串。
        current_user (User): 当前登录用户对象。
        current_student (Student): 当前学生。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await TeachingClassService(db).confirm_join(token, current_user, current_student.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
