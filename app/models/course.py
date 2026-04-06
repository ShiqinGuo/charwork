from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class CourseStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Course(Base):
    __tablename__ = "course"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    teaching_class_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("teaching_class.id"),
        nullable=False,
        index=True,
    )
    teacher_id: Mapped[str] = mapped_column(String(50), ForeignKey("teacher.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[CourseStatus] = mapped_column(String(20), nullable=False, default=CourseStatus.ACTIVE)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    teaching_class: Mapped["TeachingClass"] = relationship("TeachingClass", back_populates="courses")  # noqa
    teacher: Mapped["Teacher"] = relationship("Teacher")  # noqa
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="course")  # noqa

    def __repr__(self):
        """
        功能描述：
            处理Course。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<Course(name='{self.name}', management_system_id='{self.management_system_id}')>"
