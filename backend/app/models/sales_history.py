from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.inventory_transaction import InventoryTransaction


class SalesHistory(Base, TimestampMixin):
    """
    SQLAlchemy model representing sales history records for catalog products.

    Rules:
    - product_id: Foreign key to products.id with CASCADE deletion.
    - transaction_id: Foreign key to inventory_transactions.id for physical movement traceability.
    - quantity: Number of units sold (> 0).
    - unit_price: Snapshot of product catalog price at the moment of sale.
    - total_amount: Total monetary value of the sale (quantity * unit_price).
    - sale_date: UTC timestamp of the sale event for time-series demand analysis.
    """
    __tablename__ = "sales_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    transaction_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("inventory_transactions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    sale_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="sales_history")
    transaction: Mapped[Optional["InventoryTransaction"]] = relationship("InventoryTransaction")

    def __repr__(self) -> str:
        return (
            f"<SalesHistory id={self.id} "
            f"product_id={self.product_id} "
            f"transaction_id={self.transaction_id} "
            f"qty={self.quantity} "
            f"unit_price={self.unit_price} "
            f"total_amount={self.total_amount} "
            f"sale_date={self.sale_date!r}>"
        )
