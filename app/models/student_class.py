from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class StudentClassStatus(str, PyEnum):
    """学生班级关系状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class StudentClass(Base):
    """学生与班级的关系模型"""
    __tablename__ = "student_class"
    __table_args__ = (
        UniqueConstraint("student_id", "teaching_class_id", name="uq_student_class"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    student_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("student.id"),
        nullable=False,
        index=True,
    )
    teaching_class_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("teaching_class.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[StudentClassStatus] = mapped_column(
        String(20),
        nullable=False,
        default=StudentClassStatus.ACTIVE,
    )
    joined_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    student: Mapped["Student"] = relationship("Student", back_populates="student_classes")  # noqa
    teaching_class: Mapped["TeachingClass"] = relationship("TeachingClass", back_populates="student_classes")  # noqa

    def __repr__(self):
        """
        功能描述：
            处理StudentClass。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<StudentClass(student_id='{self.student_id}', teaching_class_id='{self.teaching_class_id}')>"
