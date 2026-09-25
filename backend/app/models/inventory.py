from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin


class Inventory(Base, TimestampMixin):
    """
    SQLAlchemy model representing current inventory stock levels for a product.

    Rules:
    - product_id: Unique foreign key to products.id (1-to-1 relationship).
    - on_hand: Total physical units currently present in warehouse (>= 0).
    - reserved: Units committed to orders/replenishments but not yet dispatched (>= 0).
    - incoming: Units ordered from suppliers and expected in warehouse (>= 0).
    - available_stock: Derived in Python as (on_hand - reserved). Not stored in DB.
    - Database constraints enforce:
        on_hand >= 0
        reserved >= 0
        incoming >= 0
        reserved <= on_hand
    """
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="ck_inventory_on_hand_non_negative"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_non_negative"),
        CheckConstraint("incoming >= 0", name="ck_inventory_incoming_non_negative"),
        CheckConstraint("reserved <= on_hand", name="ck_inventory_reserved_le_on_hand"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    on_hand: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    reserved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    incoming: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="inventory")

    @property
    def available_stock(self) -> int:
        """
        Dynamically derived available stock quantity for replenishment and sales.
        Guaranteed to be non-negative by reserved <= on_hand invariant.
        """
        return self.on_hand - self.reserved

    def __repr__(self) -> str:
        return (
            f"<Inventory id={self.id} "
            f"product_id={self.product_id} "
            f"on_hand={self.on_hand} "
            f"reserved={self.reserved} "
            f"incoming={self.incoming} "
            f"available_stock={self.available_stock}>"
        )
