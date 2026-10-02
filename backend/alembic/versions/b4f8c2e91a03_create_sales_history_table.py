"""create sales history table

Revision ID: b4f8c2e91a03
Revises: a8d2e4f71b9c
Create Date: 2026-09-26 08:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f8c2e91a03'
down_revision: Union[str, None] = 'a8d2e4f71b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sales_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('sale_date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['inventory_transactions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sales_history_id'), 'sales_history', ['id'], unique=False)
    op.create_index(op.f('ix_sales_history_product_id'), 'sales_history', ['product_id'], unique=False)
    op.create_index(op.f('ix_sales_history_transaction_id'), 'sales_history', ['transaction_id'], unique=False)
    op.create_index(op.f('ix_sales_history_sale_date'), 'sales_history', ['sale_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sales_history_sale_date'), table_name='sales_history')
    op.drop_index(op.f('ix_sales_history_transaction_id'), table_name='sales_history')
    op.drop_index(op.f('ix_sales_history_product_id'), table_name='sales_history')
    op.drop_index(op.f('ix_sales_history_id'), table_name='sales_history')
    op.drop_table('sales_history')
