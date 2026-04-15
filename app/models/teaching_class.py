from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class TeachingClassStatus(str, PyEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TeachingClassMemberStatus(str, PyEnum):
    ACTIVE = "active"
    LEFT = "left"


class TeachingClassJoinTokenStatus(str, PyEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    USED_UP = "used_up"


class TeachingClass(Base):
    __tablename__ = "teaching_class"
    __table_args__ = (
        UniqueConstraint("management_system_id", "teacher_id", "name", name="uq_teaching_class_scope_name"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    teacher_id: Mapped[str] = mapped_column(String(50), ForeignKey("teacher.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TeachingClassStatus] = mapped_column(
        String(20),
        nullable=False,
        default=TeachingClassStatus.ACTIVE,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    teacher: Mapped["Teacher"] = relationship("Teacher")  # noqa
    courses: Mapped[list["Course"]] = relationship("Course", back_populates="teaching_class")  # noqa
    members: Mapped[list["TeachingClassMember"]] = relationship(
        "TeachingClassMember",
        back_populates="teaching_class",
        cascade="all, delete-orphan",
    )
    join_tokens: Mapped[list["TeachingClassJoinToken"]] = relationship(
        "TeachingClassJoinToken",
        back_populates="teaching_class",
        cascade="all, delete-orphan",
    )
    student_classes: Mapped[list["StudentClass"]] = relationship("StudentClass", back_populates="teaching_class")  # noqa

    def __repr__(self):
        """
        功能描述：
            处理TeachingClass。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<TeachingClass(name='{self.name}', management_system_id='{self.management_system_id}')>"


class TeachingClassMember(Base):
    __tablename__ = "teaching_class_member"
    __table_args__ = (
        UniqueConstraint("teaching_class_id", "student_id", name="uq_teaching_class_member"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    teaching_class_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("teaching_class.id"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey("student.id"), nullable=False, index=True)
    joined_by_token_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("teaching_class_join_token.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[TeachingClassMemberStatus] = mapped_column(
        String(20),
        nullable=False,
        default=TeachingClassMemberStatus.ACTIVE,
    )
    joined_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    teaching_class: Mapped["TeachingClass"] = relationship("TeachingClass", back_populates="members")  # noqa
    student: Mapped["Student"] = relationship("Student")  # noqa
    joined_by_token: Mapped[Optional["TeachingClassJoinToken"]] = relationship(
        "TeachingClassJoinToken",
        back_populates="member_joins",
    )  # noqa

    def __repr__(self):
        """
        功能描述：
            处理TeachingClassMember。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<TeachingClassMember(teaching_class_id='{self.teaching_class_id}', student_id='{self.student_id}')>"


class TeachingClassJoinToken(Base):
    __tablename__ = "teaching_class_join_token"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    teaching_class_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("teaching_class.id"),
        nullable=False,
        index=True,
    )
    created_by_teacher_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("teacher.id"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[TeachingClassJoinTokenStatus] = mapped_column(
        String(20),
        nullable=False,
        default=TeachingClassJoinTokenStatus.ACTIVE,
    )
    last_used_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    teaching_class: Mapped["TeachingClass"] = relationship("TeachingClass", back_populates="join_tokens")  # noqa
    creator: Mapped["Teacher"] = relationship("Teacher")  # noqa
    member_joins: Mapped[list["TeachingClassMember"]] = relationship(
        "TeachingClassMember",
        back_populates="joined_by_token",
    )  # noqa

    def __repr__(self):
        """
        功能描述：
            处理TeachingClassJoinToken。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<TeachingClassJoinToken(teaching_class_id='{self.teaching_class_id}', token='{self.token}')>"
