from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Integer, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class AssignmentTemplate(Base):
    __tablename__ = "assignment_template"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    teacher_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    character_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    course_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    due_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AssignmentTemplate(id='{self.id}', name='{self.name}')>"
