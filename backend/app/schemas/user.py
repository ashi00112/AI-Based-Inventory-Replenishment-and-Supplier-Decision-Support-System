"""
Pydantic schemas for administrative user management and RBAC.
"""

from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.user import UserRole
from app.schemas.auth import UserResponse


class AdminUserCreate(BaseModel):
    """
    Payload for creating new user accounts by an Administrator.
    Supports assigning role: ADMIN or STAFF.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Full name of the user",
    )
    email: EmailStr = Field(
        ...,
        description="Unique corporate email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Initial password for the account (minimum 8 characters)",
    )
    role: str = Field(
        default="STAFF",
        description="Assigned role: ADMIN or STAFF",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Name cannot be empty or whitespace only.")
            return stripped
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            return "STAFF"
        normalized = v.strip().upper()
        if normalized == "USER":
            normalized = "STAFF"
        if normalized not in ("ADMIN", "STAFF"):
            raise ValueError(f"Invalid role '{v}'. Allowed roles are ADMIN and STAFF.")
        return normalized


class AdminUserUpdate(BaseModel):
    """
    Payload for modifying an existing user account by an Administrator.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Optional new password")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Name cannot be empty or whitespace only.")
            return stripped
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Role must be a string.")
        normalized = v.strip().upper()
        if normalized == "USER":
            normalized = "STAFF"
        if normalized not in ("ADMIN", "STAFF"):
            raise ValueError(f"Invalid role '{v}'. Allowed roles are ADMIN and STAFF.")
        return normalized


class UserListResponse(BaseModel):
    """
    Paginated user list payload for administrative user management.
    """
    items: List[UserResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total count of matching users")

    model_config = ConfigDict(
        from_attributes=True,
    )
