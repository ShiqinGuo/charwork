"""
为什么这样做：注册流程在同一事务内完成用户、角色档案与默认管理系统初始化，避免半初始化账号。
特殊逻辑：登录时补偿默认系统实体，兼容历史账号未初始化场景，收敛边界数据差异。
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student
from app.repositories.user_repo import UserRepository
from app.services.management_system_service import ManagementSystemService


class UserService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化UserService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.repo = UserRepository(db)

    async def register(
        self, *, username: str, email: str,
        password: str, role: str, name: str,
        department: Optional[str], class_name: Optional[str]
    ) -> User:
        """
        功能描述：
            注册UserService。

        参数：
            username (str): 字符串结果。
            email (str): 字符串结果。
            password (str): 字符串结果。
            role (str): 角色信息。
            name (str): 字符串结果。
            department (Optional[str]): 字符串结果。
            class_name (Optional[str]): 字符串结果。

        返回值：
            User: 返回User类型的处理结果。
        """
        existing = await self.repo.get_by_username(username)
        if existing:
            raise ValueError("用户名已存在")

        existing_email = await self.repo.get_by_email(email)
        if existing_email:
            raise ValueError("邮箱已存在")

        try:
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                role=UserRole.TEACHER if role == "teacher" else UserRole.STUDENT,
                is_active=True,
            )
            self.db.add(user)
            await self.db.flush()

            if role == "teacher":
                teacher = Teacher(user_id=user.id, name=name, department=department)
                self.db.add(teacher)
            else:
                student = Student(user_id=user.id, name=name, class_name=class_name)
                self.db.add(student)

            await ManagementSystemService(self.db).ensure_default_system_entity(user, commit=False)
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception:
            await self.db.rollback()
            raise

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        功能描述：
            处理UserService。

        参数：
            username (str): 字符串结果。
            password (str): 字符串结果。

        返回值：
            Optional[User]: 返回处理结果对象；无可用结果时返回 None。
        """
        user = await self.repo.get_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        await ManagementSystemService(self.db).ensure_default_system_entity(user)
        return user
