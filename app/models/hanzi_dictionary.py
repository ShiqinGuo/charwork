from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class HanziDictionary(Base):
    __tablename__ = "hanzi_dictionary"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    character: Mapped[str] = mapped_column(String(1), nullable=False, unique=True, index=True)
    stroke_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stroke_pattern: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    pinyin: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="strokes_txt")
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class HanziDataset(Base):
    __tablename__ = "hanzi_dataset"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class HanziDatasetItem(Base):
    __tablename__ = "hanzi_dataset_item"
    __table_args__ = (
        UniqueConstraint("dataset_id", "dictionary_id", name="uq_dataset_dictionary"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    dataset_id: Mapped[str] = mapped_column(String(50), ForeignKey("hanzi_dataset.id"), nullable=False, index=True)
    hanzi_id: Mapped[str] = mapped_column(
        "dictionary_id",
        String(50),
        ForeignKey("hanzi.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
