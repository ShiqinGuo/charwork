from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class AIChatConversation(Base):
    __tablename__ = "ai_chat_conversation"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    teacher_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    management_system_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    messages: Mapped[list["AIChatMessage"]] = relationship(
        "AIChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    memory_facts: Mapped[list["AIChatMemoryFact"]] = relationship(
        "AIChatMemoryFact",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AIChatMessage(Base):
    __tablename__ = "ai_chat_message"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    conversation_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ai_chat_conversation.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls_json: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    conversation: Mapped["AIChatConversation"] = relationship(
        "AIChatConversation",
        back_populates="messages",
    )  # noqa
    memory_facts: Mapped[list["AIChatMemoryFact"]] = relationship(
        "AIChatMemoryFact",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class AIChatMemoryFact(Base):
    __tablename__ = "ai_chat_memory_fact"
    __table_args__ = (
        UniqueConstraint("conversation_id", "message_id", "fact_key", name="uq_ai_chat_memory_fact_conv_msg_key"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    conversation_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ai_chat_conversation.id"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ai_chat_message.id"),
        nullable=False,
        index=True,
    )
    teacher_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    management_system_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("student.id"), nullable=True, index=True)
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fact_value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    conversation: Mapped["AIChatConversation"] = relationship(
        "AIChatConversation",
        back_populates="memory_facts",
    )  # noqa
    message: Mapped["AIChatMessage"] = relationship(
        "AIChatMessage",
        back_populates="memory_facts",
    )  # noqa
