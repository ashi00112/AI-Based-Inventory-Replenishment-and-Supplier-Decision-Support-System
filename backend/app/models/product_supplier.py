from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.supplier import Supplier


class ProductSupplier(Base, TimestampMixin):
    """
    SQLAlchemy model representing a specific supplier's commercial offer for a catalog product.

    Rules:
    - product_id: Foreign key to products.id (CASCADE).
    - supplier_id: Foreign key to suppliers.id (CASCADE).
    - supplier_sku: Optional supplier-specific catalog or part number.
    - unit_cost: Supplier's agreed wholesale/procurement unit cost (>= 0).
    - moq: Minimum Order Quantity (>= 1).
    - lead_time_days: Expected replenishment lead time in days (>= 0).
    - is_active: Toggle for whether this commercial offer is currently orderable.
    - UniqueConstraint(product_id, supplier_id): Ensures at most one active commercial link per pair.
    """
    __tablename__ = "product_suppliers"
    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier"),
        CheckConstraint("unit_cost >= 0", name="ck_product_supplier_unit_cost_non_negative"),
        CheckConstraint("moq >= 1", name="ck_product_supplier_moq_min_one"),
        CheckConstraint("lead_time_days >= 0", name="ck_product_supplier_lead_time_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    supplier_sku: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    moq: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="supplier_offers")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="product_offers")

    def __repr__(self) -> str:
        return (
            f"<ProductSupplier id={self.id} "
            f"product_id={self.product_id} "
            f"supplier_id={self.supplier_id} "
            f"cost={self.unit_cost} "
            f"moq={self.moq} "
            f"lead_time={self.lead_time_days}d "
            f"is_active={self.is_active}>"
        )
