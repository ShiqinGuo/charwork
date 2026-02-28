from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.user import User
from app.models.assignment import Assignment


class Teacher(Base):
    __tablename__ = "teacher"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="teacher_profile")
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="teacher")

    def __repr__(self):
        return f"<Teacher(name='{self.name}', department='{self.department}')>"
