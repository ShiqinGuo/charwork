from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class ManagementSystemAccessRole(str, PyEnum):
    OWNER = "owner"
    VIEWER = "viewer"


class ManagementSystem(Base):
    __tablename__ = "management_system"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "preset_key", name="uq_management_system_owner_preset"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    owner_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_type: Mapped[str] = mapped_column(String(50), nullable=False, default="custom", index=True)
    preset_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    owner_user: Mapped["User"] = relationship("User", back_populates="owned_management_systems")  # noqa
    user_links: Mapped[list["UserManagementSystem"]] = relationship(
        "UserManagementSystem",
        back_populates="management_system",
        cascade="all, delete-orphan",
    )
    records: Mapped[list["ManagementSystemRecord"]] = relationship(
        "ManagementSystemRecord",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        """
        功能描述：
            处理ManagementSystem。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<ManagementSystem(name='{self.name}', owner_user_id='{self.owner_user_id}')>"


class UserManagementSystem(Base):
    __tablename__ = "user_management_system"
    __table_args__ = (
        UniqueConstraint("user_id", "management_system_id", name="uq_user_management_system_link"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    access_role: Mapped[ManagementSystemAccessRole] = mapped_column(
        String(20),
        nullable=False,
        default=ManagementSystemAccessRole.OWNER,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="management_system_links")  # noqa
    management_system: Mapped["ManagementSystem"] = relationship("ManagementSystem", back_populates="user_links")

    def __repr__(self):
        """
        功能描述：
            处理UserManagementSystem。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<UserManagementSystem(user_id='{self.user_id}', management_system_id='{self.management_system_id}')>"
