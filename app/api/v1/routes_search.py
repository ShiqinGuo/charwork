from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_admin, get_current_user

from app.core.database import get_db
from app.core.security import SessionUser
from app.models.user import User, UserRole
from app.schemas.search import CrossSearchResponse, PermissionContext, ReindexResponse
from app.services.cross_search_service import CrossSearchService


router = APIRouter()


async def _build_permission_context(
    current_user: User,
    db: AsyncSession,
) -> PermissionContext:
    from app.repositories.course_repo import CourseRepository
    from app.repositories.student_repo import StudentRepository
    from app.repositories.teaching_class_repo import TeachingClassRepository

    if current_user.role == UserRole.ADMIN:
        return PermissionContext(role="admin")

    if current_user.role == UserRole.TEACHER:
        return PermissionContext(role="teacher", user_id=current_user.id)

    # 学生：预查课程和班级
    student = await StudentRepository(db).get_by_user_id(current_user.id)
    if not student:
        return PermissionContext(role="student", user_id=current_user.id)
    course_ids = await CourseRepository(db).list_ids_for_student(student.id)
    class_ids = await TeachingClassRepository(db).list_ids_for_student(student.id)
    return PermissionContext(
        role="student",
        user_id=current_user.id,
        student_user_id=current_user.id,
        course_ids=course_ids,
        class_ids=class_ids,
    )


@router.get("/", response_model=CrossSearchResponse)
async def cross_search(
    keyword: str = Query(..., min_length=1),
    modules: Optional[list[str]] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: SessionUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理检索。

    参数：
        keyword (str): 字符串结果。
        modules (Optional[list[str]]): 列表结果。
        limit (int): 单次查询的最大返回数量。
        current_user (SessionUser): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        perm_ctx = await _build_permission_context(current_user, db)
        return await CrossSearchService(db).search(
            keyword=keyword,
            current_user=current_user,
            modules=modules,
            limit=limit,
            permission_ctx=perm_ctx,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"检索服务不可用：{str(e)}")


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_search(
    _current_admin: SessionUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    功能描述：
        处理检索。

    参数：
        _current_admin (SessionUser): SessionUser 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    try:
        return await CrossSearchService(db).reindex()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"重建索引失败：{str(e)}")


@router.get("/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1, description="搜索关键词，支持部分输入"),
    modules: str | None = Query(None, description="逗号分隔的模块名"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """实时搜索建议，debounce 调用。"""
    module_list = [m.strip() for m in modules.split(",") if m.strip()] if modules else None
    return await CrossSearchService(db).suggest(
        q=q, current_user=current_user, modules=module_list,
    )
