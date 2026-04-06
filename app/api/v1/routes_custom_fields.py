from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.repositories.management_system_repo import ManagementSystemRepository
from app.schemas.custom_field import (
    ManagementSystemCustomFieldCreate,
    ManagementSystemCustomFieldListResponse,
    ManagementSystemCustomFieldResponse,
    ManagementSystemCustomFieldSearchResponse,
    ManagementSystemCustomFieldValueListResponse,
    ManagementSystemCustomFieldValueUpsertRequest,
)
from app.services.custom_field_service import CustomFieldService


router = APIRouter()


async def _ensure_management_system_access(
    management_system_id: str,
    current_user: User,
    db: AsyncSession,
) -> None:
    # 统一在路由入口做可访问性校验，避免后续查询路径在不同分支出现权限边界漂移。
    """
    功能描述：
        确保管理系统access存在，必要时自动补齐。

    参数：
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    item = await ManagementSystemRepository(db).get_accessible(management_system_id, current_user.id)
    if not item:
        raise HTTPException(status_code=403, detail="无权访问该管理系统")


@router.get("/{management_system_id}/custom-fields", response_model=ManagementSystemCustomFieldListResponse)
async def list_custom_fields(
    management_system_id: str,
    target_type: Optional[str] = Query(None),
    searchable_only: bool = Query(False),
    viewer_role: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询自定义字段列表。

    参数：
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        target_type (Optional[str]): 字符串结果。
        searchable_only (bool): 布尔值结果。
        viewer_role (Optional[str]): 角色信息。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    await _ensure_management_system_access(management_system_id, current_user, db)
    if current_user.role == UserRole.STUDENT:
        # 学生端强制按本人角色过滤可见字段，忽略外部传入 viewer_role，防止越权探测教师字段配置。
        viewer_role = current_user.role
    return await CustomFieldService(db).list_fields(
        management_system_id,
        target_type,
        viewer_role=viewer_role,
        searchable_only=searchable_only,
    )


@router.post(
    "/{management_system_id}/custom-fields",
    response_model=ManagementSystemCustomFieldResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_field(
    management_system_id: str,
    body: ManagementSystemCustomFieldCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建自定义字段并返回结果。

    参数：
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        body (ManagementSystemCustomFieldCreate): 接口请求体对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    await _ensure_management_system_access(management_system_id, current_user, db)
    if current_user.role == UserRole.STUDENT:
        # 字段定义属于配置层写操作，学生仅允许读取与填写，禁止修改结构性元数据。
        raise HTTPException(status_code=403, detail="仅教师或管理员可配置自定义字段")
    try:
        return await CustomFieldService(db).create_field(management_system_id, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{management_system_id}/custom-field-values/{target_type}/{target_id}",
    response_model=ManagementSystemCustomFieldValueListResponse,
)
async def list_custom_field_values(
    management_system_id: str,
    target_type: str,
    target_id: str,
    viewer_role: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询自定义字段值列表。

    参数：
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        target_type (str): 字符串结果。
        target_id (str): targetID。
        viewer_role (Optional[str]): 角色信息。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    await _ensure_management_system_access(management_system_id, current_user, db)
    if current_user.role == UserRole.STUDENT:
        # 对学生场景固定查询视角，保证值读取与字段列表使用同一权限模型。
        viewer_role = current_user.role
    return await CustomFieldService(db).list_values(
        management_system_id,
        target_type,
        target_id,
        viewer_role=viewer_role,
    )


@router.get(
    "/{management_system_id}/custom-field-search/{target_type}",
    response_model=ManagementSystemCustomFieldSearchResponse,
)
async def search_custom_field_values(
    management_system_id: str,
    target_type: str,
    field_key: str = Query(..., min_length=1),
    keyword: str = Query(..., min_length=1),
    viewer_role: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        检索自定义字段值。

    参数：
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        target_type (str): 字符串结果。
        field_key (str): 字符串结果。
        keyword (str): 字符串结果。
        viewer_role (Optional[str]): 角色信息。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    await _ensure_management_system_access(management_system_id, current_user, db)
    if current_user.role == UserRole.STUDENT:
        # 搜索接口可被用于侧信道枚举，学生调用时必须锁定 viewer_role 避免扩大检索范围。
        viewer_role = current_user.role
    try:
        return await CustomFieldService(db).search_values(
            management_system_id,
            target_type,
            field_key,
            keyword,
            viewer_role=viewer_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/{management_system_id}/custom-field-values/{target_type}/{target_id}",
    response_model=ManagementSystemCustomFieldValueListResponse,
)
async def upsert_custom_field_values(
    management_system_id: str,
    target_type: str,
    target_id: str,
    body: ManagementSystemCustomFieldValueUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        新增或更新自定义字段值。

    参数：
        management_system_id (str): 管理系统ID，用于限制数据作用域。
        target_type (str): 字符串结果。
        target_id (str): targetID。
        body (ManagementSystemCustomFieldValueUpsertRequest): 接口请求体对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    await _ensure_management_system_access(management_system_id, current_user, db)
    try:
        return await CustomFieldService(db).upsert_values(
            management_system_id,
            target_type,
            target_id,
            current_user.id,
            body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
