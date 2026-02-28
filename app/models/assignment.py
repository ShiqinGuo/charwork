from typing import Optional, List
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, func, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.teacher import Teacher
from app.models.submission import Submission


class AssignmentStatus(str, PyEnum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    CLOSED = 'closed'


class Assignment(Base):
    __tablename__ = "assignment"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    teacher_id: Mapped[str] = mapped_column(String(50), ForeignKey("teacher.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hanzi_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    due_date: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(String(20), default=AssignmentStatus.DRAFT)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="assignments")
    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="assignment")

    def __repr__(self):
        return f"<Assignment(title='{self.title}', status='{self.status}')>"
