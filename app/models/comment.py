from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.user import User


class TargetType(str, PyEnum):
    ASSIGNMENT = 'assignment'
    SUBMISSION = 'submission'


class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False)

    target_type: Mapped[TargetType] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User")

    def __repr__(self):
        return f"<Comment(id='{self.id}', target='{self.target_type}')>"
