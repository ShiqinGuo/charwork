from enum import Enum as PyEnum
from typing import Any, Optional

from sqlalchemy import DateTime, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class AIFeedbackTargetType(str, PyEnum):
    SUBMISSION_ATTACHMENT = "submission_attachment"
    SUBMISSION = "submission"


class AIFeedbackScope(str, PyEnum):
    ATTACHMENT_ITEM = "attachment_item"
    STUDENT_SUMMARY = "student_summary"


class AIFeedbackVisibility(str, PyEnum):
    SHARED_TEACHER_STUDENT = "shared_teacher_student"
    STUDENT_ONLY = "student_only"


class AIFeedbackStatus(str, PyEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class AIFeedbackGeneratedBy(str, PyEnum):
    SYSTEM = "system"
    STUDENT = "student"


class AIFeedback(Base):
    __tablename__ = "ai_feedback"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(50), nullable=False)
    feedback_scope: Mapped[str] = mapped_column(String(50), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AIFeedbackStatus.PENDING.value)
    generated_by: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AIFeedbackGeneratedBy.SYSTEM.value,
    )
    result_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "target_type",
            "target_id",
            "feedback_scope",
            name="uq_ai_feedback_target_scope",
        ),
        Index("idx_ai_feedback_target", "target_type", "target_id"),
        Index("idx_ai_feedback_visibility", "visibility_scope", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIFeedback(id='{self.id}', target_type='{self.target_type}', "
            f"target_id='{self.target_id}', scope='{self.feedback_scope}')>"
        )
