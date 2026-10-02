"""create suppliers and product_suppliers tables

Revision ID: 5eb9e265c603
Revises: b4f8c2e91a03
Create Date: 2026-10-02 14:07:33.524523+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eb9e265c603'
down_revision: Union[str, None] = 'b4f8c2e91a03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create suppliers table
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('supplier_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('contact_name', sa.String(length=150), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_suppliers_id'), 'suppliers', ['id'], unique=False)
    op.create_index(op.f('ix_suppliers_supplier_code'), 'suppliers', ['supplier_code'], unique=True)
    op.create_index(op.f('ix_suppliers_name'), 'suppliers', ['name'], unique=False)

    # 2. Create product_suppliers table
    op.create_table(
        'product_suppliers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('supplier_sku', sa.String(length=100), nullable=True),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('moq', sa.Integer(), server_default='1', nullable=False),
        sa.Column('lead_time_days', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'supplier_id', name='uq_product_supplier'),
        sa.CheckConstraint('unit_cost >= 0', name='ck_product_supplier_unit_cost_non_negative'),
        sa.CheckConstraint('moq >= 1', name='ck_product_supplier_moq_min_one'),
        sa.CheckConstraint('lead_time_days >= 0', name='ck_product_supplier_lead_time_non_negative'),
    )
    op.create_index(op.f('ix_product_suppliers_id'), 'product_suppliers', ['id'], unique=False)
    op.create_index(op.f('ix_product_suppliers_product_id'), 'product_suppliers', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_suppliers_supplier_id'), 'product_suppliers', ['supplier_id'], unique=False)


def downgrade() -> None:
    # Drop product_suppliers first (dependent table)
    op.drop_index(op.f('ix_product_suppliers_supplier_id'), table_name='product_suppliers')
    op.drop_index(op.f('ix_product_suppliers_product_id'), table_name='product_suppliers')
    op.drop_index(op.f('ix_product_suppliers_id'), table_name='product_suppliers')
    op.drop_table('product_suppliers')

    # Drop suppliers second
    op.drop_index(op.f('ix_suppliers_name'), table_name='suppliers')
    op.drop_index(op.f('ix_suppliers_supplier_code'), table_name='suppliers')
    op.drop_index(op.f('ix_suppliers_id'), table_name='suppliers')
    op.drop_table('suppliers')
