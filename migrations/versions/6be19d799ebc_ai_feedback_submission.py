"""ai_feedback_submission

Revision ID: 6be19d799ebc
Revises: d1f4c9a7b321
Create Date: 2026-04-15 23:45:26.970864

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6be19d799ebc'
down_revision = 'd1f4c9a7b321'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('submission', 'feedback',
                    new_column_name='teacher_feedback',
                    existing_type=sa.Text(),
                    existing_nullable=True,
                    nullable=True)
    op.add_column('submission', sa.Column('ai_feedback', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('submission', 'ai_feedback')
    op.alter_column('submission', 'teacher_feedback',
                    new_column_name='feedback',
                    existing_type=sa.Text(),
                    existing_nullable=True,
                    nullable=True)
