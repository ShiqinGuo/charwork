"""
学生班级路由模块。

为学生提供班级相关的 API 端点，包括加入班级、查询班级列表等功能。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_student
from app.core.database import get_db
from app.models.student import Student
from app.schemas.student_class import StudentClassJoinResponse, StudentClassListResponse
from app.services.student_class_service import StudentClassService


router = APIRouter()


class JoinClassRequest(BaseModel):
    """加入班级请求体"""
    teaching_class_id: str


@router.post("/me/join-class", response_model=StudentClassJoinResponse, status_code=status.HTTP_201_CREATED)
async def join_class(
    body: JoinClassRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        学生加入班级。

    参数：
        body (JoinClassRequest): 接口请求体对象，包含班级ID。
        current_student (Student): 当前登录的学生。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        StudentClassJoinResponse: 返回加入班级的响应对象。

    异常：
        HTTPException(400): teaching_class_id 为空。
        HTTPException(409): 学生已加入该班级。
        HTTPException(404): 班级不存在。
    """
    if not body.teaching_class_id:
        raise HTTPException(status_code=400, detail="teaching_class_id 为必填")

    try:
        result = await StudentClassService(db).join_class(
            current_student.id, body.teaching_class_id
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "学生已加入该班级" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        elif "班级不存在" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.get("/me/classes", response_model=StudentClassListResponse)
async def list_student_classes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        查看学生加入的班级列表。

    参数：
        skip (int): 分页偏移量，默认为 0。
        limit (int): 单次查询的最大返回数量，默认为 20，最大为 100。
        current_student (Student): 当前登录的学生。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        StudentClassListResponse: 返回班级列表响应对象。
    """
    return await StudentClassService(db).list_student_classes(
        current_student.id, skip=skip, limit=limit
    )


@router.get("/me/classes/{class_id}")
async def get_class_detail(
    class_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        查看班级详情。

    参数：
        class_id (str): 班级ID。
        current_student (Student): 当前登录的学生。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        dict: 返回班级详情字典。

    异常：
        HTTPException(403): 学生未加入班级。
        HTTPException(404): 班级不存在。
    """
    try:
        result = await StudentClassService(db).get_class_detail(
            current_student.id, class_id
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "学生未加入该班级" in error_msg:
            raise HTTPException(status_code=403, detail=error_msg)
        elif "班级不存在" in error_msg or "教师不存在" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.get("/me/classes/{class_id}/members")
async def get_class_members(
    class_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        查看班级成员列表。

    参数：
        class_id (str): 班级ID。
        skip (int): 分页偏移量，默认为 0。
        limit (int): 单次查询的最大返回数量，默认为 20，最大为 100。
        current_student (Student): 当前登录的学生。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        dict: 返回班级成员列表字典。

    异常：
        HTTPException(403): 学生未加入班级。
        HTTPException(404): 班级不存在。
    """
    try:
        result = await StudentClassService(db).get_class_members(
            current_student.id, class_id, skip=skip, limit=limit
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "学生未加入该班级" in error_msg:
            raise HTTPException(status_code=403, detail=error_msg)
        elif "班级不存在" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
