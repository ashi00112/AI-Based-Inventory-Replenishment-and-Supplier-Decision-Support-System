"""create documents table

Revision ID: 6dc03b462dbd
Revises: 5eb9e265c603
Create Date: 2026-10-02 16:13:34.320805+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6dc03b462dbd'
down_revision: Union[str, None] = '5eb9e265c603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), server_default='application/pdf', nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('file_size_bytes >= 1', name='ck_document_file_size_positive'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key', name='uq_documents_storage_key'),
    )
    op.create_index('ix_documents_id', 'documents', ['id'], unique=False)
    op.create_index('ix_documents_document_type', 'documents', ['document_type'], unique=False)
    op.create_index('ix_documents_supplier_id', 'documents', ['supplier_id'], unique=False)
    op.create_index('ix_documents_storage_key', 'documents', ['storage_key'], unique=True)
    op.create_index('ix_documents_sha256_checksum', 'documents', ['sha256_checksum'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_documents_sha256_checksum', table_name='documents')
    op.drop_index('ix_documents_storage_key', table_name='documents')
    op.drop_index('ix_documents_supplier_id', table_name='documents')
    op.drop_index('ix_documents_document_type', table_name='documents')
    op.drop_index('ix_documents_id', table_name='documents')
    op.drop_table('documents')
