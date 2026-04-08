from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class CustomFieldTargetType(str, PyEnum):
    COURSE = "course"
    ASSIGNMENT = "assignment"
    STUDENT = "student"


class CustomFieldType(str, PyEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    SELECT = "select"
    JSON = "json"
    FILE = "file"


class ManagementSystemCustomField(Base):
    __tablename__ = "management_system_custom_field"
    __table_args__ = (
        UniqueConstraint(
            "management_system_id",
            "target_type",
            "field_key",
            name="uq_management_system_custom_field",
        ),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    field_type: Mapped[CustomFieldType] = mapped_column(String(30), nullable=False)
    target_type: Mapped[CustomFieldTargetType] = mapped_column(String(30), nullable=False, index=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    visibility_roles: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    values: Mapped[list["ManagementSystemCustomFieldValue"]] = relationship(
        "ManagementSystemCustomFieldValue",
        back_populates="field",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        """
        功能描述：
            处理ManagementSystemCustomField。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<ManagementSystemCustomField(field_key='{self.field_key}', target_type='{self.target_type}')>"


class ManagementSystemCustomFieldValue(Base):
    __tablename__ = "management_system_custom_field_value"
    __table_args__ = (
        UniqueConstraint("field_id", "target_id", name="uq_management_system_custom_field_value"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    field_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system_custom_field.id"),
        nullable=False,
        index=True,
    )
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[CustomFieldTargetType] = mapped_column(String(30), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("user.id"), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    field: Mapped["ManagementSystemCustomField"] = relationship(
        "ManagementSystemCustomField",
        back_populates="values",
    )  # noqa

    def __repr__(self):
        """
        功能描述：
            处理ManagementSystemCustomFieldValue。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<ManagementSystemCustomFieldValue(field_id='{self.field_id}', target_id='{self.target_id}')>"
