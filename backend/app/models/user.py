import enum
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import TimestampMixin


class UserRole(str, enum.Enum):
    """
    Allowed application roles for users.
    Internal system permits only ADMIN and STAFF roles.
    USER is retained as a legacy/compatibility alias for staff.
    """
    ADMIN = "admin"
    STAFF = "staff"
    USER = "user"


class User(Base, TimestampMixin):
    """
    SQLAlchemy model representing application users and credentials foundation.
    Stores core identity attributes for future authentication without exposing
    plain-text credentials.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.USER.value,
        server_default=UserRole.USER.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} "
            f"name={self.name!r} "
            f"email={self.email!r} "
            f"role={self.role!r} "
            f"is_active={self.is_active}>"
        )
