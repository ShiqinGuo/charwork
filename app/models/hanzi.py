from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class StructureType(str, PyEnum):
    UNKNOWN = '未知结构'
    LEFT_RIGHT = '左右结构'
    UP_DOWN = '上下结构'
    SURROUND = '包围结构'
    SINGLE = '独体结构'
    PIN = '品字结构'
    INTERLACED = '穿插结构'


class VariantType(str, PyEnum):
    SIMPLIFIED = '简体'
    TRADITIONAL = '繁体'


class LevelType(str, PyEnum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'


class Hanzi(Base):
    __tablename__ = "hanzi"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    train_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    character: Mapped[str] = mapped_column(String(1), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(255), nullable=True)
    stroke_count: Mapped[int] = mapped_column(Integer, nullable=True)

    structure: Mapped[StructureType] = mapped_column(
        String(20),
        default=StructureType.UNKNOWN
    )

    stroke_order: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pinyin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    level: Mapped[LevelType] = mapped_column(String(1), nullable=True)

    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    variant: Mapped[VariantType] = mapped_column(
        String(10),
        default=VariantType.SIMPLIFIED
    )

    standard_image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Hanzi(character='{self.character}', id='{self.id}')>"
