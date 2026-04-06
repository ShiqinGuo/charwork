from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.management_system import (
    ManagementSystemCreate,
    ManagementSystemListResponse,
    ManagementSystemResponse,
    ManagementSystemUpdate,
)
from app.services.management_system_service import ManagementSystemService


router = APIRouter()


@router.get("/mine", response_model=ManagementSystemListResponse)
async def list_my_management_systems(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 列表仅返回“当前用户可见集合”，分页边界在路由层限制，避免一次请求穿透过多授权关系。
    """
    功能描述：
        按条件查询my管理systems列表。

    参数：
        skip (int): 分页偏移量。
        limit (int): 单次查询的最大返回数量。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await ManagementSystemService(db).list_my_systems(current_user, skip, limit)


@router.get("/default", response_model=ManagementSystemResponse)
async def get_default_management_system(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取默认管理系统。

    参数：
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await ManagementSystemService(db).get_default_system(current_user)


@router.get("/{id}", response_model=ManagementSystemResponse)
async def get_management_system_detail(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取管理系统detail。

    参数：
        id (str): 目标记录ID。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    item = await ManagementSystemService(db).get_system_detail(id, current_user)
    if not item:
        raise HTTPException(status_code=404, detail="管理系统不存在")
    return item


@router.post("/", response_model=ManagementSystemResponse, status_code=status.HTTP_201_CREATED)
async def create_management_system(
    body: ManagementSystemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建管理系统并返回结果。

    参数：
        body (ManagementSystemCreate): 接口请求体对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await ManagementSystemService(db).create_custom_system(current_user, body)
    except PermissionError as exc:
        # 权限拒绝统一翻译为 403，避免把越权写操作误暴露成业务字段错误。
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.put("/{id}", response_model=ManagementSystemResponse)
async def update_management_system(
    id: str,
    body: ManagementSystemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        更新管理系统并返回最新结果。

    参数：
        id (str): 目标记录ID。
        body (ManagementSystemUpdate): 接口请求体对象。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = ManagementSystemService(db)
    try:
        item = await service.update_custom_system(id, current_user, body)
    except PermissionError as exc:
        # 更新链路优先表达权限边界，调用方可据此与 400 参数错误做明确分流处理。
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not item:
        raise HTTPException(status_code=404, detail="管理系统不存在")

    return item
