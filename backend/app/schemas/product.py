from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCreate(BaseModel):
    """
    Schema for creating a new product catalog item.
    Rejects blank or whitespace-only SKU and name, and ensures non-negative numbers.
    Disallows client input for id, created_at, or updated_at.
    """
    sku: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique business Stock Keeping Unit identifier",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name of the product",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Product category group",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional detailed product description",
    )
    unit_price: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Unit selling/catalog price, must be >= 0",
    )
    reorder_point: int = Field(
        default=0,
        ge=0,
        description="Inventory threshold triggering replenishment, must be >= 0",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("sku", mode="before")
    @classmethod
    def validate_sku(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("SKU cannot be blank or only whitespace.")
            return stripped
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Product name cannot be blank or only whitespace.")
            return stripped
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class ProductUpdate(BaseModel):
    """
    Schema for partial updates to an existing product.
    All fields are optional; any supplied values must satisfy domain constraints.
    """
    sku: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Updated unique SKU identifier",
    )
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Updated display name",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated category group",
    )
    description: Optional[str] = Field(
        default=None,
        description="Updated product description",
    )
    unit_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Updated unit price, must be >= 0",
    )
    reorder_point: Optional[int] = Field(
        default=None,
        ge=0,
        description="Updated reorder point, must be >= 0",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Active status of the product in the catalog",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("sku", mode="before")
    @classmethod
    def validate_sku(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("SKU cannot be blank or only whitespace.")
            return stripped
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Product name cannot be blank or only whitespace.")
            return stripped
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class ProductResponse(BaseModel):
    """
    Public schema for Product data representation.
    """
    id: int
    sku: str
    name: str
    category: Optional[str]
    description: Optional[str]
    unit_price: Decimal
    reorder_point: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
