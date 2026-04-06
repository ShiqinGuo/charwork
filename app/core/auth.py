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
        提取bearer令牌。

    参数：
        authorization (str | None): 字符串结果。

    返回值：
        str: 返回str类型的处理结果。
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
        按条件获取当前令牌。

    参数：
        authorization (str | None): 字符串结果。

    返回值：
        str: 返回查询到的结果对象。
    """
    return extract_bearer_token(authorization)


async def get_current_user(
    token: str = Depends(get_current_token),
) -> SessionUser:
    """
    功能描述：
        按条件获取当前用户。

    参数：
        token (str): 令牌字符串。

    返回值：
        SessionUser: 返回查询到的结果对象。
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
        按条件获取当前教师。

    参数：
        current_user (SessionUser): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        Teacher: 返回查询到的结果对象。
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
        按条件获取当前admin。

    参数：
        current_user (SessionUser): 当前登录用户对象。

    返回值：
        SessionUser: 返回查询到的结果对象。
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
        按条件获取当前学生。

    参数：
        current_user (SessionUser): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        Student: 返回查询到的结果对象。
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="仅学生可执行该操作")

    student = await StudentRepository(db).get_by_user_id(current_user.id)
    if not student:
        raise HTTPException(status_code=404, detail="学生档案不存在")

    return student
