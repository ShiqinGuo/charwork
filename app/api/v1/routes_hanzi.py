from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_admin, get_current_user, get_current_teacher
from app.core.database import get_db
from app.core.management_scope import ManagementScope, get_management_scope
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.hanzi import HanziResponse, HanziListResponse, HanziCreate, HanziUpdate
from app.schemas.hanzi_dictionary import (
    HanziDatasetCreate,
    HanziDatasetListResponse,
    HanziDatasetResponse,
    HanziDictionaryInitRequest,
    HanziDictionaryInitResponse,
    HanziDictionaryListResponse,
    HanziDictionaryResponse,
)
from app.services.hanzi_dictionary_service import HanziDictionaryService
from app.services.hanzi_service import HanziService
from app.utils.pagination import resolve_pagination
from app.core.config import settings

router = APIRouter()


@router.get("/", response_model=HanziListResponse)
async def list_hanzi(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    structure: Optional[str] = None,
    level: Optional[str] = None,
    variant: Optional[str] = None,
    search: Optional[str] = None,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询汉字列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        structure (Optional[str]): 字符串结果。
        level (Optional[str]): 字符串结果。
        variant (Optional[str]): 字符串结果。
        search (Optional[str]): 字符串结果。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await service.list_hanzi(
        skip=pagination["skip"],
        limit=pagination["limit"],
        structure=structure,
        level=level,
        variant=variant,
        search=search,
        management_system_id=scope.management_system_id,
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/", response_model=HanziResponse)
async def create_hanzi(
    hanzi_in: HanziCreate,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建汉字并返回结果。

    参数：
        hanzi_in (HanziCreate): 汉字输入对象。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    return await service.create_hanzi(hanzi_in, scope.management_system_id)


@router.get("/strokes/{character}")
async def get_strokes(character: str, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        按条件获取strokes。

    参数：
        character (str): 字符串结果。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    return service.get_strokes(character)


@router.get("/stroke-search", response_model=HanziListResponse)
async def stroke_search(
    pattern: str = Query(..., min_length=1),
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理检索。

    参数：
        pattern (str): 字符串结果。
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await service.search_by_stroke_order(
        pattern,
        pagination["skip"],
        pagination["limit"],
        scope.management_system_id,
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/dictionary/initialize", response_model=HanziDictionaryInitResponse)
async def initialize_dictionary(
    body: HanziDictionaryInitRequest,
    _current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        初始化字典。

    参数：
        body (HanziDictionaryInitRequest): 接口请求体对象。
        _current_admin (User): User 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziDictionaryService(db)
    return await service.initialize_from_strokes(settings.STROKES_FILE_PATH, force=body.force)


@router.get("/dictionary", response_model=HanziDictionaryListResponse)
async def list_dictionary_entries(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    character: Optional[str] = Query(None),
    pinyin: Optional[str] = Query(None),
    stroke_count: Optional[int] = Query(None, ge=1),
    stroke_pattern: Optional[str] = Query(None, min_length=1),
    keyword: Optional[str] = Query(None),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询字典条目列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        character (Optional[str]): 字符串结果。
        pinyin (Optional[str]): 字符串结果。
        stroke_count (Optional[int]): 数量值。
        stroke_pattern (Optional[str]): 字符串结果。
        keyword (Optional[str]): 字符串结果。
        _current_user (User): User 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await HanziDictionaryService(db).list_dictionary_entries(
        skip=pagination["skip"],
        limit=pagination["limit"],
        page=pagination["page"],
        size=pagination["size"],
        character=character,
        pinyin=pinyin,
        stroke_count=stroke_count,
        stroke_pattern=stroke_pattern,
        keyword=keyword,
    )


@router.get("/dictionary/{id}", response_model=HanziDictionaryResponse)
async def get_dictionary_entry(
    id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取字典条目。

    参数：
        id (str): 目标记录ID。
        _current_user (User): User 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    entry = await HanziDictionaryService(db).get_dictionary_entry(id)
    if not entry:
        raise HTTPException(status_code=404, detail="共享汉字字典记录不存在")
    return entry


@router.get("/datasets", response_model=HanziDatasetListResponse)
async def list_hanzi_datasets(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询汉字数据集列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await HanziDictionaryService(db).list_datasets(
        management_system_id=scope.management_system_id,
        skip=pagination["skip"],
        limit=pagination["limit"],
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/datasets", response_model=HanziDatasetResponse)
async def create_hanzi_dataset(
    body: HanziDatasetCreate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建汉字数据集并返回结果。

    参数：
        body (HanziDatasetCreate): 接口请求体对象。
        scope (ManagementScope): 管理系统作用域对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await HanziDictionaryService(db).create_dataset(
        management_system_id=scope.management_system_id,
        created_by_user_id=current_teacher.user_id,
        body=body,
    )


@router.get("/{id}", response_model=HanziResponse)
async def get_hanzi(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取汉字。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    hanzi = await service.get_hanzi(id, scope.management_system_id)
    if not hanzi:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return hanzi


@router.put("/{id}", response_model=HanziResponse)
async def update_hanzi(
    id: str,
    hanzi_in: HanziUpdate,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        更新汉字并返回最新结果。

    参数：
        id (str): 目标记录ID。
        hanzi_in (HanziUpdate): 汉字输入对象。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    hanzi = await service.update_hanzi(id, hanzi_in, scope.management_system_id)
    if not hanzi:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return hanzi


@router.delete("/{id}")
async def delete_hanzi(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        删除汉字。

    参数：
        id (str): 目标记录ID。
        scope (ManagementScope): 管理系统作用域对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = HanziService(db)
    success = await service.delete_hanzi(id, scope.management_system_id)
    if not success:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return {"status": "success"}
