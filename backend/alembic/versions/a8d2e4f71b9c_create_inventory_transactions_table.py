"""create inventory transactions table

Revision ID: a8d2e4f71b9c
Revises: f3a8b1c4e921
Create Date: 2026-09-25 13:45:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d2e4f71b9c'
down_revision: Union[str, None] = 'f3a8b1c4e921'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('previous_on_hand', sa.Integer(), nullable=False),
        sa.Column('new_on_hand', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inventory_transactions_id'), 'inventory_transactions', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_product_id'), 'inventory_transactions', ['product_id'], unique=False)
    op.create_index(op.f('ix_inventory_transactions_transaction_type'), 'inventory_transactions', ['transaction_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_transactions_transaction_type'), table_name='inventory_transactions')
    op.drop_index(op.f('ix_inventory_transactions_product_id'), table_name='inventory_transactions')
    op.drop_index(op.f('ix_inventory_transactions_id'), table_name='inventory_transactions')
    op.drop_table('inventory_transactions')
