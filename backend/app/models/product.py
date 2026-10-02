from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin


class Product(Base, TimestampMixin):
    """
    SQLAlchemy model representing catalog products.

    Rules:
    - sku: Unique, required business identifier for the product.
    - name: Required descriptive title.
    - unit_price: Non-negative decimal value representing selling/catalog price.
    - reorder_point: Minimum inventory threshold before replenishment triggers.
    - is_active: Catalog status toggle.
    - Inventory quantities (on_hand, reserved, etc.) belong to future Inventory model, not here.
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )
    reorder_point: Mapped[int] = mapped_column(
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

    # 1-to-1 relationship with inventory
    inventory: Mapped[Optional["Inventory"]] = relationship(
        "Inventory",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # 1-to-many relationship with historical inventory transactions
    transactions: Mapped[list["InventoryTransaction"]] = relationship(
        "InventoryTransaction",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # 1-to-many relationship with sales history records
    sales_history: Mapped[list["SalesHistory"]] = relationship(
        "SalesHistory",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # 1-to-many relationship with supplier commercial offers
    supplier_offers: Mapped[list["ProductSupplier"]] = relationship(
        "ProductSupplier",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Product id={self.id} "
            f"sku={self.sku!r} "
            f"name={self.name!r} "
            f"category={self.category!r} "
            f"unit_price={self.unit_price} "
            f"reorder_point={self.reorder_point} "
            f"is_active={self.is_active}>"
        )
