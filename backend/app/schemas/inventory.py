from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductSummary(BaseModel):
    """
    Concise product representation embedded in inventory responses.
    Provides necessary catalog context (SKU, name, reorder point) without overhead.
    """
    id: int
    sku: str
    name: str
    reorder_point: int

    model_config = ConfigDict(
        from_attributes=True,
    )


class InventoryCreate(BaseModel):
    """
    Schema for initializing an inventory record.
    Used during product creation or initial setup.
    """
    product_id: int = Field(..., description="ID of the associated product")
    on_hand: int = Field(default=0, ge=0, description="Physical units on hand (>= 0)")
    reserved: int = Field(default=0, ge=0, description="Committed units reserved (>= 0)")
    incoming: int = Field(default=0, ge=0, description="Expected incoming units (>= 0)")

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="after")
    def validate_stock_balance(self) -> "InventoryCreate":
        if self.reserved > self.on_hand:
            raise ValueError("Reserved stock cannot exceed on-hand stock.")
        return self


class InventoryUpdate(BaseModel):
    """
    Schema for updating stock values on an existing inventory record.
    All fields are optional; any supplied values must be non-negative.
    available_stock cannot be directly modified by the client.
    """
    on_hand: Optional[int] = Field(
        default=None,
        ge=0,
        description="Physical units on hand (must be >= 0)",
    )
    reserved: Optional[int] = Field(
        default=None,
        ge=0,
        description="Units committed/reserved (must be >= 0)",
    )
    incoming: Optional[int] = Field(
        default=None,
        ge=0,
        description="Incoming units ordered from suppliers (must be >= 0)",
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="after")
    def validate_update_balance(self) -> "InventoryUpdate":
        if self.on_hand is not None and self.reserved is not None:
            if self.reserved > self.on_hand:
                raise ValueError("Reserved stock cannot exceed on-hand stock.")
        return self


class InventoryResponse(BaseModel):
    """
    Public representation of inventory stock levels.
    available_stock is derived dynamically as (on_hand - reserved).
    """
    id: int
    product_id: int
    on_hand: int
    reserved: int
    incoming: int
    available_stock: int
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductSummary] = None

    model_config = ConfigDict(
        from_attributes=True,
    )
