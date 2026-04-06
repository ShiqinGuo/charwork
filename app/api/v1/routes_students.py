from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate
from app.services.student_service import StudentService


router = APIRouter()


@router.get("/")
async def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询学生列表。

    参数：
        skip (int): 分页偏移量。
        limit (int): 单次查询的最大返回数量。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await StudentService(db).list_students(skip, limit)


@router.post("/", response_model=StudentResponse)
async def create_student(body: StudentCreate, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        创建学生并返回结果。

    参数：
        body (StudentCreate): 接口请求体对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    return await StudentService(db).create_student(body)


@router.get("/{id}", response_model=StudentResponse)
async def get_student(id: str, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        按条件获取学生。

    参数：
        id (str): 目标记录ID。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    student = await StudentService(db).get_student(id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.put("/{id}", response_model=StudentResponse)
async def update_student(id: str, body: StudentUpdate, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        更新学生并返回最新结果。

    参数：
        id (str): 目标记录ID。
        body (StudentUpdate): 接口请求体对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    student = await StudentService(db).update_student(id, body)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.delete("/{id}")
async def delete_student(id: str, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        删除学生。

    参数：
        id (str): 目标记录ID。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    ok = await StudentService(db).delete_student(id)
    if not ok:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {"status": "success"}
