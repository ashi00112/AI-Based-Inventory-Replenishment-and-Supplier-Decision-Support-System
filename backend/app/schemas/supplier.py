from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SupplierBase(BaseModel):
    """
    Base schema containing shared supplier properties.
    """
    supplier_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique business identifier for supplier (e.g. SUP-001)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Supplier legal or trade business name",
    )
    contact_name: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Primary contact person name",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Valid contact email address",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Contact telephone number",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Physical or postal business address",
    )
    is_active: bool = Field(
        default=True,
        description="Active vendor status toggle",
    )

    @field_validator("supplier_code")
    @classmethod
    def normalize_supplier_code(cls, v: str) -> str:
        code = v.strip().upper()
        if not code:
            raise ValueError("Supplier code cannot be empty.")
        return code

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("Supplier name cannot be empty.")
        return name


class SupplierCreate(SupplierBase):
    """
    Schema for creating a new supplier.
    """
    model_config = ConfigDict(
        extra="forbid",
    )


class SupplierUpdate(BaseModel):
    """
    Schema for partially updating an existing supplier.
    """
    supplier_code: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Unique business identifier for supplier",
    )
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Supplier business name",
    )
    contact_name: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Primary contact person name",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Valid contact email address",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Contact telephone number",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Physical or postal business address",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Active vendor status toggle",
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @field_validator("supplier_code")
    @classmethod
    def normalize_supplier_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            code = v.strip().upper()
            if not code:
                raise ValueError("Supplier code cannot be empty.")
            return code
        return None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            name = v.strip()
            if not name:
                raise ValueError("Supplier name cannot be empty.")
            return name
        return None


class SupplierSummary(BaseModel):
    """
    Compact supplier overview for embedding in offers.
    """
    id: int
    supplier_code: str
    name: str
    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
    )


class SupplierResponse(BaseModel):
    """
    Public representation of a supplier record.
    """
    id: int
    supplier_code: str
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
