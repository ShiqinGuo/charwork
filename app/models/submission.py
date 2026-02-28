from typing import Optional, List
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Text, DateTime, func, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.assignment import Assignment
from app.models.student import Student


class SubmissionStatus(str, PyEnum):
    SUBMITTED = 'submitted'
    GRADED = 'graded'


class Submission(Base):
    __tablename__ = "submission"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    assignment_id: Mapped[str] = mapped_column(String(50), ForeignKey("assignment.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey("student.id"), nullable=False)

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_paths: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    status: Mapped[SubmissionStatus] = mapped_column(String(20), default=SubmissionStatus.SUBMITTED)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    graded_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    assignment: Mapped["Assignment"] = relationship("Assignment", back_populates="submissions")
    student: Mapped["Student"] = relationship("Student", back_populates="submissions")

    # 评论为多态关联（作业/提交），当前采用目标编号 + 目标类型方式在业务层查询

    def __repr__(self):
        return f"<Submission(id='{self.id}', status='{self.status}')>"
