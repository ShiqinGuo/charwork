from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class AssignmentAttachmentUpload(Base):
    __tablename__ = "assignment_attachment_upload"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("assignment.id"),
        nullable=True,
        index=True,
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )
