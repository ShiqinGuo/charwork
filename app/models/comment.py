from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, Text, DateTime, func, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class TargetType(str, PyEnum):
    ASSIGNMENT = 'assignment'
    SUBMISSION = 'submission'


class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False)

    target_type: Mapped[TargetType] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    root_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    reply_to_user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="comments")  # noqa

    def __repr__(self):
        """
        功能描述：
            处理Comment。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<Comment(id='{self.id}', target='{self.target_type}')>"
