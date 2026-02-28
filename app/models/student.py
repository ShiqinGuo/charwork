from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id

from app.models.user import User
from app.models.submission import Submission


class Student(Base):
    __tablename__ = "student"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    class_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="student_profile")
    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="student")

    def __repr__(self):
        return f"<Student(name='{self.name}', class_name='{self.class_name}')>"
