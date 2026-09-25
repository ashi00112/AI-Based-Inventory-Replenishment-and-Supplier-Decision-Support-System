from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.inventory_transaction import InventoryTransactionType
from app.schemas.inventory import ProductSummary


class InventoryTransactionCreate(BaseModel):
    """
    Schema for creating/recording a new inventory transaction.
    Client supplies product, type, quantity, and optional note.
    Stock levels and audit timestamps are strictly server-managed.
    """
    product_id: int = Field(..., description="ID of the catalog product")
    transaction_type: InventoryTransactionType = Field(
        ...,
        description="Type of transaction: sale, restock, return, or adjustment",
    )
    quantity: int = Field(..., description="Units to process. Positive for sale/restock/return; signed non-zero for adjustment.")
    note: Optional[str] = Field(default=None, max_length=500, description="Optional reason, order reference, or context")

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="after")
    def validate_quantity_by_type(self) -> "InventoryTransactionCreate":
        ttype = self.transaction_type
        qty = self.quantity

        if ttype in (
            InventoryTransactionType.SALE,
            InventoryTransactionType.RESTOCK,
            InventoryTransactionType.RETURN,
        ):
            if qty <= 0:
                raise ValueError(
                    f"Quantity for {ttype.value.upper()} must be strictly greater than 0."
                )

        elif ttype == InventoryTransactionType.ADJUSTMENT:
            if qty == 0:
                raise ValueError("Quantity for ADJUSTMENT cannot be zero.")

        return self


class InventoryTransactionResponse(BaseModel):
    """
    Public representation of an immutable historical inventory transaction.
    """
    id: int
    product_id: int
    transaction_type: InventoryTransactionType
    quantity: int
    previous_on_hand: int
    new_on_hand: int
    note: Optional[str] = None
    created_at: datetime
    product: Optional[ProductSummary] = None

    model_config = ConfigDict(
        from_attributes=True,
    )
