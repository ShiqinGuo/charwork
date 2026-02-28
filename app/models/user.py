from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.teacher import Teacher
from app.models.student import Student
from app.models.message import Message


class UserRole(str, PyEnum):
    TEACHER = 'teacher'
    STUDENT = 'student'
    ADMIN = 'admin'


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.STUDENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # 角色扩展关系
    teacher_profile: Mapped[Optional["Teacher"]] = relationship("Teacher", back_populates="user", uselist=False)
    student_profile: Mapped[Optional["Student"]] = relationship("Student", back_populates="user", uselist=False)

    # 消息关系
    sent_messages: Mapped[list["Message"]] = relationship(
        "Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages: Mapped[list["Message"]] = relationship(
        "Message", foreign_keys="Message.receiver_id", back_populates="receiver")

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role}')>"
