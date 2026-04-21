"""iteration1.1

Revision ID: 854bd91bd688
Revises: b1bc58f5f262
Create Date: 2026-04-07 12:46:03.020135

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '854bd91bd688'
down_revision = 'b1bc58f5f262'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('hanzi', sa.Column('dictionary_id', sa.String(length=50), nullable=True))
    op.add_column('hanzi', sa.Column('stroke_pattern', sa.String(length=255), nullable=True))
    op.add_column('hanzi', sa.Column('source', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_hanzi_dictionary_id'), 'hanzi', ['dictionary_id'], unique=False)
    op.create_index(op.f('ix_hanzi_stroke_pattern'), 'hanzi', ['stroke_pattern'], unique=False)
    op.create_foreign_key('fk_hanzi_dictionary_id_hanzi_dictionary', 'hanzi',
                          'hanzi_dictionary', ['dictionary_id'], ['id'])
    op.execute('DELETE FROM hanzi_dataset_item')
    op.drop_constraint(op.f('hanzi_dataset_item_ibfk_2'), 'hanzi_dataset_item', type_='foreignkey')
    op.create_foreign_key('fk_hanzi_dataset_item_hanzi_id', 'hanzi_dataset_item', 'hanzi', ['dictionary_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_hanzi_dataset_item_hanzi_id', 'hanzi_dataset_item', type_='foreignkey')
    op.create_foreign_key(
        op.f('hanzi_dataset_item_ibfk_2'),
        'hanzi_dataset_item',
        'hanzi_dictionary',
        ['dictionary_id'],
        ['id'])
    op.drop_constraint('fk_hanzi_dictionary_id_hanzi_dictionary', 'hanzi', type_='foreignkey')
    op.drop_index(op.f('ix_hanzi_stroke_pattern'), table_name='hanzi')
    op.drop_index(op.f('ix_hanzi_dictionary_id'), table_name='hanzi')
    op.drop_column('hanzi', 'source')
    op.drop_column('hanzi', 'stroke_pattern')
    op.drop_column('hanzi', 'dictionary_id')
