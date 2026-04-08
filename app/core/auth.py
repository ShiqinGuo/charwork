"""
认证依赖注入模块。

为 FastAPI 路由提供当前用户身份解析的 Depends 依赖，包括：
- 通用用户鉴权（get_current_user）
- 按角色鉴权（get_current_teacher / get_current_student / get_current_admin）
"""

from fastapi import Depends, Header, HTTPException
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import SessionUser, get_session_user
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import UserRole
from app.repositories.student_repo import StudentRepository
from app.repositories.teacher_repo import TeacherRepository


def extract_bearer_token(authorization: str | None) -> str:
    """
    功能描述：
        从 Authorization 请求头中提取 Bearer 令牌字符串。

    参数：
        authorization (str | None): 原始 Authorization 头部值，形如 "Bearer <token>"。

    返回值：
        str: 提取出的令牌字符串。

    异常：
        HTTPException(401): 缺少或格式错误时抛出。
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization")
    # 只按首次空格拆分，兼容 token 字符串中可能包含额外空白的边界输入。
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 格式错误")
    return parts[1]


async def get_current_token(
    authorization: str | None = Header(default=None),
) -> str:
    """
    功能描述：
        FastAPI 依赖：从请求头解析并返回 Bearer 令牌，供下游鉴权使用。

    参数：
        authorization (str | None): HTTP Authorization 请求头。

    返回值：
        str: 令牌字符串。
    """
    return extract_bearer_token(authorization)


async def get_current_user(
    token: str = Depends(get_current_token),
) -> SessionUser:
    """
    功能描述：
        FastAPI 依赖：通过令牌从 Redis 会话中获取当前登录用户信息，
        同时自动续期会话，并校验用户是否被禁用。

    参数：
        token (str): Bearer 令牌字符串。

    返回值：
        SessionUser: 当前登录用户的会话信息。

    异常：
        HTTPException(401): 会话已过期或无效。
        HTTPException(403): 用户已被禁用。
        HTTPException(503): Redis 服务不可用。
    """
    try:
        # 鉴权阶段统一续期，减少高频接口下会话被动过期导致的重复登录。
        user = await get_session_user(token, extend_expire=True)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="会话服务不可用") from exc
    if not user:
        raise HTTPException(status_code=401, detail="会话已过期或无效")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已禁用")
    return user


async def get_current_teacher(
    current_user: SessionUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Teacher:
    """
    功能描述：
        FastAPI 依赖：校验当前用户为教师角色，并从数据库查询对应的教师档案。

    参数：
        current_user (SessionUser): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        Teacher: 教师实体对象。

    异常：
        HTTPException(403): 非教师角色。
        HTTPException(404): 教师档案不存在。
    """
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="仅教师可执行该操作")

    teacher = await TeacherRepository(db).get_by_user_id(current_user.id)
    if not teacher:
        raise HTTPException(status_code=404, detail="教师档案不存在")

    return teacher


async def get_current_admin(
    current_user: SessionUser = Depends(get_current_user),
) -> SessionUser:
    """
    功能描述：
        FastAPI 依赖：校验当前用户为管理员角色。

    参数：
        current_user (SessionUser): 当前登录用户对象。

    返回值：
        SessionUser: 管理员用户的会话信息。

    异常：
        HTTPException(403): 非管理员角色。
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可执行该操作")
    return current_user


async def get_current_student(
    current_user: SessionUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Student:
    """
    功能描述：
        FastAPI 依赖：校验当前用户为学生角色，并从数据库查询对应的学生档案。

    参数：
        current_user (SessionUser): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        Student: 学生实体对象。

    异常：
        HTTPException(403): 非学生角色。
        HTTPException(404): 学生档案不存在。
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="仅学生可执行该操作")

    student = await StudentRepository(db).get_by_user_id(current_user.id)
    if not student:
        raise HTTPException(status_code=404, detail="学生档案不存在")

    return student
