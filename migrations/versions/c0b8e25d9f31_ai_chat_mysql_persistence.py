"""ai chat mysql persistence

Revision ID: c0b8e25d9f31
Revises: 854bd91bd688
Create Date: 2026-04-07 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c0b8e25d9f31"
down_revision = "854bd91bd688"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_conversation",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("teacher_user_id", sa.String(length=50), nullable=False),
        sa.Column("management_system_id", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["management_system_id"], ["management_system.id"]),
        sa.ForeignKeyConstraint(["teacher_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_chat_conversation_teacher_scope_updated", "ai_chat_conversation",
                    ["teacher_user_id", "management_system_id", "updated_at"], unique=False)
    op.create_index(op.f("ix_ai_chat_conversation_is_deleted"), "ai_chat_conversation", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_ai_chat_conversation_management_system_id"),
                    "ai_chat_conversation", ["management_system_id"], unique=False)
    op.create_index(
        op.f("ix_ai_chat_conversation_teacher_user_id"),
        "ai_chat_conversation",
        ["teacher_user_id"],
        unique=False)

    op.create_table(
        "ai_chat_message",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("conversation_id", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls_json", sa.JSON(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_chat_conversation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_chat_message_conversation_created_at", "ai_chat_message",
                    ["conversation_id", "created_at"], unique=False)
    op.create_index(op.f("ix_ai_chat_message_conversation_id"), "ai_chat_message", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_message_created_at"), "ai_chat_message", ["created_at"], unique=False)
    op.create_index(op.f("ix_ai_chat_message_is_deleted"), "ai_chat_message", ["is_deleted"], unique=False)

    op.create_table(
        "ai_chat_memory_fact",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("conversation_id", sa.String(length=50), nullable=False),
        sa.Column("message_id", sa.String(length=50), nullable=False),
        sa.Column("teacher_user_id", sa.String(length=50), nullable=False),
        sa.Column("management_system_id", sa.String(length=50), nullable=True),
        sa.Column("student_id", sa.String(length=50), nullable=True),
        sa.Column("fact_type", sa.String(length=50), nullable=False),
        sa.Column("fact_key", sa.String(length=120), nullable=False),
        sa.Column("fact_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_chat_conversation.id"]),
        sa.ForeignKeyConstraint(["management_system_id"], ["management_system.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["ai_chat_message.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["teacher_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "message_id", "fact_key", name="uq_ai_chat_memory_fact_conv_msg_key"),
    )
    op.create_index(
        op.f("ix_ai_chat_memory_fact_conversation_id"),
        "ai_chat_memory_fact",
        ["conversation_id"],
        unique=False)
    op.create_index(op.f("ix_ai_chat_memory_fact_management_system_id"),
                    "ai_chat_memory_fact", ["management_system_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_memory_fact_message_id"), "ai_chat_memory_fact", ["message_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_memory_fact_student_id"), "ai_chat_memory_fact", ["student_id"], unique=False)
    op.create_index(
        op.f("ix_ai_chat_memory_fact_teacher_user_id"),
        "ai_chat_memory_fact",
        ["teacher_user_id"],
        unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_chat_memory_fact_teacher_user_id"), table_name="ai_chat_memory_fact")
    op.drop_index(op.f("ix_ai_chat_memory_fact_student_id"), table_name="ai_chat_memory_fact")
    op.drop_index(op.f("ix_ai_chat_memory_fact_message_id"), table_name="ai_chat_memory_fact")
    op.drop_index(op.f("ix_ai_chat_memory_fact_management_system_id"), table_name="ai_chat_memory_fact")
    op.drop_index(op.f("ix_ai_chat_memory_fact_conversation_id"), table_name="ai_chat_memory_fact")
    op.drop_table("ai_chat_memory_fact")

    op.drop_index(op.f("ix_ai_chat_message_is_deleted"), table_name="ai_chat_message")
    op.drop_index(op.f("ix_ai_chat_message_created_at"), table_name="ai_chat_message")
    op.drop_index(op.f("ix_ai_chat_message_conversation_id"), table_name="ai_chat_message")
    op.drop_index("ix_ai_chat_message_conversation_created_at", table_name="ai_chat_message")
    op.drop_table("ai_chat_message")

    op.drop_index(op.f("ix_ai_chat_conversation_teacher_user_id"), table_name="ai_chat_conversation")
    op.drop_index(op.f("ix_ai_chat_conversation_management_system_id"), table_name="ai_chat_conversation")
    op.drop_index(op.f("ix_ai_chat_conversation_is_deleted"), table_name="ai_chat_conversation")
    op.drop_index("ix_ai_chat_conversation_teacher_scope_updated", table_name="ai_chat_conversation")
    op.drop_table("ai_chat_conversation")
