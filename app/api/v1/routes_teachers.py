from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.services.teacher_service import TeacherService


router = APIRouter()


@router.get("/")
async def list_teachers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询教师列表。

    参数：
        skip (int): 分页偏移量。
        limit (int): 单次查询的最大返回数量。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await TeacherService(db).list_teachers(skip, limit)


@router.post("/", response_model=TeacherResponse)
async def create_teacher(body: TeacherCreate, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        创建教师并返回结果。

    参数：
        body (TeacherCreate): 接口请求体对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await TeacherService(db).create_teacher(body)


@router.get("/{id}", response_model=TeacherResponse)
async def get_teacher(id: str, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        按条件获取教师。

    参数：
        id (str): 目标记录ID。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    teacher = await TeacherService(db).get_teacher(id)
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")
    return teacher


@router.put("/{id}", response_model=TeacherResponse)
async def update_teacher(id: str, body: TeacherUpdate, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        更新教师并返回最新结果。

    参数：
        id (str): 目标记录ID。
        body (TeacherUpdate): 接口请求体对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    teacher = await TeacherService(db).update_teacher(id, body)
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")
    return teacher


@router.delete("/{id}")
async def delete_teacher(id: str, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        删除教师。

    参数：
        id (str): 目标记录ID。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    ok = await TeacherService(db).delete_teacher(id)
    if not ok:
        raise HTTPException(status_code=404, detail="教师不存在")
    return {"status": "success"}
