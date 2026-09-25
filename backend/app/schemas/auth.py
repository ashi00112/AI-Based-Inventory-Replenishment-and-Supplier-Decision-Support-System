from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.user import UserRole


class UserRegister(BaseModel):
    """
    Schema for user self-registration.
    Strictly forbids role, is_active, and password_hash assignment by public users.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Full name of the user",
    )
    email: EmailStr = Field(
        ...,
        description="Unique, valid user email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password (minimum 8 characters, maximum 128 characters)",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_and_validate_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Name cannot be empty or only whitespace.")
            return stripped
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserLogin(BaseModel):
    """
    Schema for user credentials login payload.
    """
    email: EmailStr = Field(
        ...,
        description="User email address",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="User plain-text password",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserResponse(BaseModel):
    """
    Schema for public user profile data representations.
    Excludes password and password_hash fields and supports ORM hydration.
    """
    id: int
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class TokenResponse(BaseModel):
    """
    Schema for JWT access token response payload.
    """
    access_token: str = Field(..., description="Encoded JWT access token string")
    token_type: str = Field(default="bearer", description="Token type, defaults to 'bearer'")


class TokenPayload(BaseModel):
    """
    Schema representing validated claims inside a decoded JWT access token.
    Provides type-safe access to sub, token type, timestamps, and integer user_id.
    """
    sub: str = Field(..., description="Subject identifier (string user ID)")
    type: str = Field(..., description="Token type, e.g. 'access'")
    iat: datetime = Field(..., description="Token issuance UTC timestamp")
    exp: datetime = Field(..., description="Token expiration UTC timestamp")

    @property
    def user_id(self) -> int:
        """Helper property to access the subject as an integer ID."""
        return int(self.sub)

    def __getitem__(self, item: str) -> Any:
        """Allows dictionary-style subscript access for backward compatibility."""
        return getattr(self, item)

