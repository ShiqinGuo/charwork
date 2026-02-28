from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student
from app.repositories.user_repo import UserRepository


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def register(
        self, *, username: str, email: str,
        password: str, role: str, name: str,
        department: Optional[str], class_name: Optional[str]
            ) -> User:
        existing = await self.repo.get_by_username(username)
        if existing:
            raise ValueError("用户名已存在")

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

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        user = await self.repo.get_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
