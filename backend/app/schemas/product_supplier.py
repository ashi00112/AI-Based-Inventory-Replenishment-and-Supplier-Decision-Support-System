from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.inventory import ProductSummary
from app.schemas.supplier import SupplierSummary


class ProductSupplierCreate(BaseModel):
    """
    Schema for creating a supplier commercial offer for a product.
    Requires product_id, supplier_id, non-negative unit_cost, moq >= 1, lead_time_days >= 0.
    """
    product_id: int = Field(
        ...,
        description="ID of the catalog product",
    )
    supplier_id: int = Field(
        ...,
        description="ID of the supplier offering the product",
    )
    supplier_sku: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Supplier's own catalog / item code",
    )
    unit_cost: Decimal = Field(
        ...,
        ge=0,
        description="Wholesale unit cost for procurement (must be >= 0)",
    )
    moq: int = Field(
        default=1,
        ge=1,
        description="Minimum order quantity in units (must be >= 1)",
    )
    lead_time_days: int = Field(
        default=0,
        ge=0,
        description="Expected fulfillment lead time in days (must be >= 0)",
    )
    is_active: bool = Field(
        default=True,
        description="Toggle whether this offer is active for ordering",
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @field_validator("supplier_sku")
    @classmethod
    def normalize_supplier_sku(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            sku = v.strip()
            return sku if sku else None
        return None


class ProductSupplierUpdate(BaseModel):
    """
    Schema for updating an existing product-supplier commercial offer.
    Notice: product_id and supplier_id cannot be changed via PATCH.
    """
    supplier_sku: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Supplier's own catalog / item code",
    )
    unit_cost: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Wholesale unit cost for procurement (must be >= 0)",
    )
    moq: Optional[int] = Field(
        default=None,
        ge=1,
        description="Minimum order quantity in units (must be >= 1)",
    )
    lead_time_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Expected fulfillment lead time in days (must be >= 0)",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Toggle whether this offer is active for ordering",
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @field_validator("supplier_sku")
    @classmethod
    def normalize_supplier_sku(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            sku = v.strip()
            return sku if sku else None
        return None


class ProductSupplierResponse(BaseModel):
    """
    Public representation of a product-supplier commercial offer.
    Includes nested product and supplier summaries for convenient frontend display.
    """
    id: int
    product_id: int
    supplier_id: int
    supplier_sku: Optional[str] = None
    unit_cost: Decimal
    moq: int
    lead_time_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductSummary] = None
    supplier: Optional[SupplierSummary] = None

    model_config = ConfigDict(
        from_attributes=True,
    )
