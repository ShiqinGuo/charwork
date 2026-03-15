from sqlalchemy import String, DateTime, func, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class CommentLike(Base):
    __tablename__ = "comment_like"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_like_comment_user"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    comment_id: Mapped[str] = mapped_column(String(50), ForeignKey("comment.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
