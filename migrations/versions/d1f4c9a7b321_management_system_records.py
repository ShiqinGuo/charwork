"""management system records

Revision ID: d1f4c9a7b321
Revises: c0b8e25d9f31
Create Date: 2026-04-07 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d1f4c9a7b321"
down_revision = "c0b8e25d9f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "management_system_record",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("management_system_id", sa.String(length=50), nullable=False),
        sa.Column("owner_user_id", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["management_system_id"], ["management_system.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_management_system_record_management_system_id"),
                    "management_system_record", ["management_system_id"], unique=False)
    op.create_index(
        op.f("ix_management_system_record_owner_user_id"),
        "management_system_record",
        ["owner_user_id"],
        unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_management_system_record_owner_user_id"), table_name="management_system_record")
    op.drop_index(op.f("ix_management_system_record_management_system_id"), table_name="management_system_record")
    op.drop_table("management_system_record")
