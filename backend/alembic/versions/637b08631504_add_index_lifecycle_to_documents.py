"""add_index_lifecycle_to_documents

Revision ID: 637b08631504
Revises: 6dc03b462dbd
Create Date: 2026-10-03 04:49:07.123799+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '637b08631504'
down_revision: Union[str, None] = '6dc03b462dbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('index_status', sa.String(length=50), server_default='not_indexed', nullable=False),
    )
    op.add_column(
        'documents',
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('index_error', sa.String(length=500), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('index_version', sa.String(length=50), server_default='v1', nullable=True),
    )
    op.create_index('ix_documents_index_status', 'documents', ['index_status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_documents_index_status', table_name='documents')
    op.drop_column('documents', 'index_version')
    op.drop_column('documents', 'index_error')
    op.drop_column('documents', 'last_indexed_at')
    op.drop_column('documents', 'index_status')

