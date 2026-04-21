from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_admin, get_current_user, get_current_teacher
from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.hanzi import (
    HanziCreate,
    HanziListResponse,
    HanziOCRBatchPrefillResponse,
    HanziOCRPrefillResponse,
    HanziResponse,
    HanziUpdate,
)
from app.schemas.hanzi_dictionary import (
    HanziDatasetAppendItemsRequest,
    HanziDatasetAppendItemsResponse,
    HanziDatasetCreate,
    HanziDatasetCreateHanziRequest,
    HanziDatasetCreateHanziResponse,
    HanziDatasetDetailResponse,
    HanziDatasetItemsListResponse,
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
    character: Optional[str] = None,
    pinyin: Optional[str] = None,
    stroke_count: Optional[int] = Query(None, ge=1),
    stroke_pattern: Optional[str] = Query(None, min_length=1),
    dataset_id: Optional[str] = None,
    source: Optional[str] = None,
    structure: Optional[str] = None,
    level: Optional[str] = None,
    variant: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
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
        current_user (User): 当前登录用户对象。
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
        character=character,
        pinyin=pinyin,
        stroke_count=stroke_count,
        stroke_pattern=stroke_pattern,
        dataset_id=dataset_id,
        source=source,
        current_user_id=current_user.id,
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/", response_model=HanziResponse)
async def create_hanzi(
    hanzi_in: HanziCreate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = HanziService(db)
    try:
        return await service.create_hanzi(hanzi_in, current_teacher.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
    current_user: User = Depends(get_current_user),
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
        current_user (User): 当前登录用户对象。
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
        current_user.id,
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
    current_user: User = Depends(get_current_user),
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
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    return await HanziDictionaryService(db).list_datasets(
        current_user_id=current_user.id,
        skip=pagination["skip"],
        limit=pagination["limit"],
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/datasets", response_model=HanziDatasetResponse)
async def create_hanzi_dataset(
    body: HanziDatasetCreate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await HanziDictionaryService(db).create_dataset(
            created_by_user_id=current_teacher.user_id,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/datasets/{dataset_id}", response_model=HanziDatasetDetailResponse)
async def get_hanzi_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await HanziDictionaryService(db).get_dataset(dataset_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/datasets/{dataset_id}/items", response_model=HanziDatasetItemsListResponse)
async def list_hanzi_dataset_items(
    dataset_id: str,
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    try:
        return await HanziDictionaryService(db).list_dataset_items(
            dataset_id=dataset_id,
            current_user_id=current_user.id,
            skip=pagination["skip"],
            limit=pagination["limit"],
            page=pagination["page"],
            size=pagination["size"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/datasets/{dataset_id}/items", response_model=HanziDatasetAppendItemsResponse)
async def append_hanzi_dataset_items(
    dataset_id: str,
    body: HanziDatasetAppendItemsRequest,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await HanziDictionaryService(db).append_dataset_items(
            dataset_id=dataset_id,
            current_user_id=current_teacher.user_id,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/datasets/{dataset_id}/hanzi", response_model=HanziDatasetCreateHanziResponse)
async def create_hanzi_in_dataset(
    dataset_id: str,
    body: HanziDatasetCreateHanziRequest,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = HanziDictionaryService(db)
    try:
        return await service.create_hanzi_in_dataset(
            dataset_id=dataset_id,
            current_user_id=current_teacher.user_id,
            hanzi_in=body.hanzi,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/datasets/{dataset_id}")
async def delete_hanzi_dataset(
    dataset_id: str,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = HanziDictionaryService(db)
    try:
        await service.delete_dataset(dataset_id, current_teacher.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "success"}


@router.post("/ocr-prefill", response_model=HanziOCRPrefillResponse)
async def ocr_prefill_hanzi(
    file: UploadFile = File(...),
    _current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = HanziService(db)
    try:
        return await service.build_prefill_by_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ocr-prefill/batch", response_model=HanziOCRBatchPrefillResponse)
async def ocr_prefill_hanzi_batch(
    files: list[UploadFile] = File(...),
    _current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = HanziService(db)
    try:
        return await service.build_batch_prefill_by_uploads(files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{id}", response_model=HanziResponse)
async def get_hanzi(
    id: str,
    current_user: User = Depends(get_current_user),
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
    hanzi = await service.get_hanzi(id, current_user.id)
    if not hanzi:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return hanzi


@router.put("/{id}", response_model=HanziResponse)
async def update_hanzi(
    id: str,
    hanzi_in: HanziUpdate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    service = HanziService(db)
    try:
        hanzi = await service.update_hanzi(id, hanzi_in, current_teacher.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not hanzi:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return hanzi


@router.delete("/{id}")
async def delete_hanzi(
    id: str,
    current_teacher: Teacher = Depends(get_current_teacher),
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
    success = await service.delete_hanzi(id, current_teacher.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="汉字不存在")
    return {"status": "success"}
