from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.product_supplier import ProductSupplier


class Supplier(Base, TimestampMixin):
    """
    SQLAlchemy model representing merchandise vendors and distributors.

    Rules:
    - supplier_code: Unique, required business identifier (e.g. SUP-001).
    - name: Required business/company name.
    - contact_name: Optional primary point-of-contact name.
    - email: Optional contact email.
    - phone: Optional contact telephone number.
    - address: Optional physical or postal address.
    - is_active: Vendor status toggle.
    - Product-specific commercial terms (unit_cost, moq, lead_time_days) belong
      to ProductSupplier, NOT directly on Supplier.
    """
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    supplier_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        index=True,
        nullable=False,
    )
    contact_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # 1-to-many relationship with ProductSupplier commercial offers
    product_offers: Mapped[list["ProductSupplier"]] = relationship(
        "ProductSupplier",
        back_populates="supplier",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Supplier id={self.id} "
            f"code={self.supplier_code!r} "
            f"name={self.name!r} "
            f"is_active={self.is_active}>"
        )
