"""
汉字数据模型模块。

定义汉字实体及其结构、变体、等级等枚举。
汉字与汉字字典、管理系统等实体建立关系映射。
"""

from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.id_generator import generate_id


class StructureType(str, PyEnum):
    """汉字结构类型枚举。"""
    UNKNOWN = '未知结构'
    LEFT_RIGHT = '左右结构'
    UP_DOWN = '上下结构'
    SURROUND = '包围结构'
    SINGLE = '独体结构'
    PIN = '品字结构'
    INTERLACED = '穿插结构'


class VariantType(str, PyEnum):
    """汉字变体类型枚举（简体/繁体）。"""
    SIMPLIFIED = '简体'
    TRADITIONAL = '繁体'


class LevelType(str, PyEnum):
    """汉字等级枚举。"""
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'


class Hanzi(Base):
    """
    汉字实体模型。

    对应数据库 hanzi 表，存储单个汉字的基本信息（字符、笔画数、结构、变体、等级等）。
    支持多租户隔离（management_system_id）和字典关联（dictionary_id）。
    """
    __tablename__ = "hanzi"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    train_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    management_system_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=True,
        index=True,
    )

    dictionary_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("hanzi_dictionary.id"),
        nullable=True,
        index=True,
    )
    character: Mapped[str] = mapped_column(String(1), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(255), nullable=True)
    stroke_count: Mapped[int] = mapped_column(Integer, nullable=True)

    structure: Mapped[StructureType] = mapped_column(
        String(20),
        default=StructureType.UNKNOWN
    )

    stroke_order: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stroke_pattern: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    pinyin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

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
        """
        功能描述：
            处理Hanzi。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<Hanzi(character='{self.character}', id='{self.id}')>"
