from typing import Optional, List, Dict, Any, TYPE_CHECKING
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Text, DateTime, func, JSON, ForeignKey, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

if TYPE_CHECKING:
    from app.models.attachment import Attachment


class SubmissionStatus(str, PyEnum):
    SUBMITTED = 'submitted'
    GRADED = 'graded'


class Submission(Base):
    __tablename__ = "submission"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    assignment_id: Mapped[str] = mapped_column(String(50), ForeignKey("assignment.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey("student.id"), nullable=False)
    management_system_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=True,
        index=True,
    )

    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[SubmissionStatus] = mapped_column(String(20), default=SubmissionStatus.SUBMITTED)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    teacher_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # AI 生成的结构化评语：{status, generated_at, items:[{image_index,char,stroke_score,...}]}
    ai_feedback: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    submitted_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    graded_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    assignment: Mapped["Assignment"] = relationship("Assignment", back_populates="submissions")  # noqa
    student: Mapped["Student"] = relationship("Student", back_populates="submissions")  # noqa
    attachments: Mapped[List["Attachment"]] = relationship(
        "Attachment",
        foreign_keys="and_(Attachment.owner_type=='submission', Attachment.owner_id==Submission.id)",
        primaryjoin="and_(Attachment.owner_type=='submission', Attachment.owner_id==Submission.id)",
        viewonly=True,
    )

    # 评论为多态关联（作业/提交），当前采用目标编号 + 目标类型方式在业务层查询

    def __repr__(self):
        return f"<Submission(id='{self.id}', status='{self.status}')>"
