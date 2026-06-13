from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher, get_current_user
from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.repositories.student_repo import StudentRepository
from app.schemas.course import CourseCreate, CourseListResponse, CourseResponse, CourseUpdate
from app.services.course_service import CourseService
from app.utils.pagination import resolve_pagination


router = APIRouter()


@router.get("/", response_model=CourseListResponse)
async def list_courses(
    skip: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    teaching_class_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件查询课程列表。

    参数：
        skip (Optional[int]): 分页偏移量。
        limit (Optional[int]): 单次查询的最大返回数量。
        page (Optional[int]): 当前页码。
        size (Optional[int]): 每页条数。
        teaching_class_id (Optional[str]): 教学班级ID。
        teacher_id (Optional[str]): 教师ID。
        status_filter (Optional[str]): 状态信息。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    pagination = resolve_pagination(page=page, size=size, skip=skip, limit=limit)
    current_student_id = None
    if current_user.role == UserRole.STUDENT:
        student = await StudentRepository(db).get_by_user_id(current_user.id)
        if not student:
            raise HTTPException(status_code=404, detail="学生档案不存在")
        current_student_id = student.id
    return await CourseService(db).list_courses(
        skip=pagination["skip"],
        limit=pagination["limit"],
        teaching_class_id=teaching_class_id,
        teacher_id=teacher_id,
        current_student_id=current_student_id,
        status=status_filter,
        page=pagination["page"],
        size=pagination["size"],
    )


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        创建课程并返回结果。

    参数：
        body (CourseCreate): 接口请求体对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await CourseService(db).create_course(body, current_teacher.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{id}", response_model=CourseResponse)
async def update_course(
    id: str,
    body: CourseUpdate,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        更新课程并返回最新结果。

    参数：
        id (str): 目标记录ID。
        body (CourseUpdate): 接口请求体对象。
        current_teacher (Teacher): 当前登录教师对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    item = await CourseService(db).get_course(id)
    if item and item.teacher_id != current_teacher.id:
        raise HTTPException(status_code=403, detail="仅可维护本人课程")
    try:
        updated = await CourseService(db).update_course(id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="课程不存在")
    return updated


@router.get("/{id}", response_model=CourseResponse)
async def get_course(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        按条件获取课程。

    参数：
        id (str): 目标记录ID。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    item = await CourseService(db).get_course(id)
    if not item:
        raise HTTPException(status_code=404, detail="课程不存在")
    if current_user.role == UserRole.STUDENT:
        student = await StudentRepository(db).get_by_user_id(current_user.id)
        if not student:
            raise HTTPException(status_code=404, detail="学生档案不存在")
        accessible_course_ids = await CourseService(db).repo.list_ids_for_student(student.id)
        if item.id not in accessible_course_ids:
            raise HTTPException(status_code=403, detail="仅可查看所属课程")
    return item
