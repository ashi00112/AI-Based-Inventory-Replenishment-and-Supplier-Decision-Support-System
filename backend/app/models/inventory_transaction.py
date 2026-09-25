from enum import Enum
from typing import Optional
from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin


class InventoryTransactionType(str, Enum):
    """
    Standard transaction classifications for recording physical stock changes.
    """
    SALE = "sale"
    RESTOCK = "restock"
    RETURN = "return"
    ADJUSTMENT = "adjustment"


class InventoryTransaction(Base, TimestampMixin):
    """
    Immutable audit ledger of stock movement events for catalog products.

    Rules:
    - Every row documents an atomic stock delta (quantity, previous_on_hand, new_on_hand).
    - SALE: positive quantity sold to customer; reduces on_hand.
    - RESTOCK: positive quantity received into warehouse; increases on_hand.
    - RETURN: positive quantity returned by customer; increases on_hand.
    - ADJUSTMENT: signed non-zero quantity for shrinkage/breakage/counting discrepancy.
    - available_stock is NOT stored here as it is derived on the inventory model.
    """
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    transaction_type: Mapped[InventoryTransactionType] = mapped_column(
        SAEnum(
            InventoryTransactionType,
            name="inventory_transaction_type",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    previous_on_hand: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    new_on_hand: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="transactions")

    def __repr__(self) -> str:
        return (
            f"<InventoryTransaction id={self.id} "
            f"product_id={self.product_id} "
            f"type={self.transaction_type.value!r} "
            f"qty={self.quantity} "
            f"on_hand={self.previous_on_hand}->{self.new_on_hand}>"
        )
