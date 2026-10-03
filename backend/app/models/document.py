import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.supplier import Supplier


class DocumentType(str, enum.Enum):
    """
    Controlled document types for SmartSupply procurement and vendor management.
    """
    PROCUREMENT_POLICY = "procurement_policy"
    INVENTORY_REPLENISHMENT_POLICY = "inventory_replenishment_policy"
    SUPPLIER_SLA = "supplier_sla"
    SUPPLIER_CONTRACT = "supplier_contract"
    SUPPLIER_PERFORMANCE_REPORT = "supplier_performance_report"
    OTHER = "other"


class IndexStatus(str, enum.Enum):
    """
    Index lifecycle status for semantic document retrieval.
    """
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    NOT_INDEXED = "not_indexed"


# Business rules for supplier-relationship association:
# - supplier_id is REQUIRED for supplier_sla, supplier_contract, supplier_performance_report
# - supplier_id is normally NULL for procurement_policy, inventory_replenishment_policy
# - supplier_id is OPTIONAL for other
SUPPLIER_REQUIRED_DOC_TYPES = {
    DocumentType.SUPPLIER_SLA.value,
    DocumentType.SUPPLIER_CONTRACT.value,
    DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
}

GENERAL_POLICY_DOC_TYPES = {
    DocumentType.PROCUREMENT_POLICY.value,
    DocumentType.INVENTORY_REPLENISHMENT_POLICY.value,
}


class Document(Base, TimestampMixin):
    """
    SQLAlchemy model representing company procurement policies and supplier documents.

    Files are stored securely in backend storage using UUID-based storage_key filenames.
    Original filenames remain metadata only for safe display and downloads.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/pdf",
        server_default="application/pdf",
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Index lifecycle tracking metadata
    index_status: Mapped[str] = mapped_column(
        String(50),
        default=IndexStatus.NOT_INDEXED.value,
        server_default="not_indexed",
        nullable=False,
        index=True,
    )
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    index_error: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    index_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        default="v1",
        server_default="v1",
        nullable=True,
    )

    # Relationships
    supplier: Mapped[Optional["Supplier"]] = relationship(
        "Supplier",
        back_populates="documents",
    )

    __table_args__ = (
        CheckConstraint("file_size_bytes >= 1", name="ck_document_file_size_positive"),
    )
