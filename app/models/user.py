"""
用户数据模型模块。

定义系统用户实体及其角色枚举，包括教师、学生、管理员三种角色。
用户与教师/学生档案、消息、评论等实体建立关系映射。
"""

from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.teacher import Teacher
from app.models.student import Student
from app.models.message import Message
from app.models.comment import Comment


class UserRole(str, PyEnum):
    """用户角色枚举。"""
    TEACHER = 'teacher'
    STUDENT = 'student'
    ADMIN = 'admin'


class User(Base):
    """
    用户实体模型。

    对应数据库 user 表，存储用户基本信息（用户名、邮箱、密码哈希、角色、激活状态）。
    支持多角色扩展（教师档案、学生档案）和关系映射（消息、评论）。
    """
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

    # 评论关系
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user")
    management_system_links: Mapped[list["UserManagementSystem"]] = relationship(
        "UserManagementSystem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    owned_management_systems: Mapped[list["ManagementSystem"]] = relationship(
        "ManagementSystem",
        back_populates="owner_user",
        foreign_keys="ManagementSystem.owner_user_id",
    )

    def __repr__(self):
        """
        功能描述：
            处理User。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<User(username='{self.username}', role='{self.role}')>"
