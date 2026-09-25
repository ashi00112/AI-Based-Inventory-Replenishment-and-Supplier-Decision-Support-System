"""create inventory table

Revision ID: f3a8b1c4e921
Revises: e5b9f71c4a20
Create Date: 2026-09-25 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a8b1c4e921'
down_revision: Union[str, None] = 'e5b9f71c4a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('on_hand', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reserved', sa.Integer(), server_default='0', nullable=False),
        sa.Column('incoming', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', name='uq_inventory_product_id'),
        sa.CheckConstraint('on_hand >= 0', name='ck_inventory_on_hand_non_negative'),
        sa.CheckConstraint('reserved >= 0', name='ck_inventory_reserved_non_negative'),
        sa.CheckConstraint('incoming >= 0', name='ck_inventory_incoming_non_negative'),
        sa.CheckConstraint('reserved <= on_hand', name='ck_inventory_reserved_le_on_hand'),
    )
    op.create_index(op.f('ix_inventory_id'), 'inventory', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_product_id'), 'inventory', ['product_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_product_id'), table_name='inventory')
    op.drop_index(op.f('ix_inventory_id'), table_name='inventory')
    op.drop_table('inventory')
