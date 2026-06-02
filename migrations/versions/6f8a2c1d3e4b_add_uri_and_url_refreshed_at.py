"""add uri and url_refreshed_at to attachment and hanzi

Revision ID: 6f8a2c1d3e4b
Revises: 4e567416dfdf
Create Date: 2026-06-02 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f8a2c1d3e4b"
down_revision: Union[str, None] = "4e567416dfdf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # attachment 表新增 uri 和 url_refreshed_at
    op.add_column("attachment", sa.Column("uri", sa.String(500), nullable=True))
    op.add_column("attachment", sa.Column("url_refreshed_at", sa.DateTime(), nullable=True))

    # hanzi 表新增 uri 和 url_refreshed_at
    op.add_column("hanzi", sa.Column("uri", sa.String(500), nullable=True))
    op.add_column("hanzi", sa.Column("url_refreshed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("hanzi", "url_refreshed_at")
    op.drop_column("hanzi", "uri")
    op.drop_column("attachment", "url_refreshed_at")
    op.drop_column("attachment", "uri")
