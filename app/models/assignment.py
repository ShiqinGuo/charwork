"""
作业数据模型模块。

定义作业实体及其状态枚举，包括草稿、已发布、截止、已归档、已关闭等状态。
作业与教师、课程、提交等实体建立关系映射。
"""

from typing import Optional, List
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, func, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class AssignmentStatus(str, PyEnum):
    """作业状态枚举。"""
    DRAFT = 'draft'
    PUBLISHED = 'published'
    DEADLINE = 'deadline'
    ARCHIVED = 'archived'
    CLOSED = 'closed'


class Assignment(Base):
    """
    作业实体模型。

    对应数据库 assignment 表，存储作业基本信息（标题、描述、汉字列表、指导步骤、附件）
    和状态信息（状态、截止日期）。支持多租户隔离（management_system_id）。
    """
    __tablename__ = "assignment"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    teacher_id: Mapped[str] = mapped_column(String(50), ForeignKey("teacher.id"), nullable=False)
    management_system_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=True,
        index=True,
    )
    course_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("course.id"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hanzi_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    instruction_steps: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    attachments: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)

    due_date: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(String(20), default=AssignmentStatus.DRAFT)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="assignments")  # noqa
    course: Mapped[Optional["Course"]] = relationship("Course", back_populates="assignments")  # noqa
    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="assignment")  # noqa

    @property
    def character_ids(self) -> Optional[List[str]]:
        """
        功能描述：
            处理标识列表。

        参数：
            无。

        返回值：
            Optional[List[str]]: 返回处理结果对象；无可用结果时返回 None。
        """
        return self.hanzi_ids

    def __repr__(self):
        """
        功能描述：
            处理Assignment。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<Assignment(title='{self.title}', status='{self.status}')>"
