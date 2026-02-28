from typing import Optional
from sqlalchemy import String, Boolean, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.user import User


class Message(Base):
    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    sender_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False)
    receiver_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False)

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver: Mapped["User"] = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")

    def __repr__(self):
        return f"<Message(id='{self.id}', title='{self.title}')>"
