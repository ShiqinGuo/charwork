"""
附件数据模型模块。

定义附件实体，支持多态关联（owner_type + owner_id），
用于存储作业、提交等实体的附件信息。
"""

from typing import Optional
from sqlalchemy import String, Integer, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class Attachment(Base):
    """
    附件实体模型。

    对应数据库 attachment 表，存储附件基本信息（文件URL、文件名、大小、MIME类型）
    和关联信息（owner_type + owner_id 实现多态关联）以及软删除（deleted_at）。
    """
    __tablename__ = "attachment"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    deleted_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_owner_type_id", "owner_type", "owner_id"),
        Index("idx_attachment_deleted_at", "deleted_at"),
    )

    def __repr__(self):
        return f"<Attachment(id='{self.id}', filename='{self.filename}', owner_type='{self.owner_type}')>"
