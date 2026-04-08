from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class ManagementSystemRecord(Base):
    __tablename__ = "management_system_record"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    management_system: Mapped["ManagementSystem"] = relationship("ManagementSystem")  # noqa

    def __repr__(self) -> str:
        return f"<ManagementSystemRecord(id='{self.id}', management_system_id='{self.management_system_id}')>"
