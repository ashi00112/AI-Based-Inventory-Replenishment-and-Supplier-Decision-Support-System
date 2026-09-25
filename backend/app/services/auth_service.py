import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import UserRegister

logger = logging.getLogger(__name__)


class UserAlreadyExistsError(Exception):
    """
    Domain exception raised when attempting to register an email address that is already in use.
    """
    pass


class AuthServiceError(Exception):
    """
    Domain exception raised when an unexpected persistence failure occurs.
    """
    pass


def create_user(db: Session, user_data: UserRegister) -> User:
    """
    Registers a new user in the database.

    1. Uses normalized email from UserRegister.
    2. Checks whether a user with the same email already exists (raises UserAlreadyExistsError).
    3. Hashes the password using Argon2id.
    4. Enforces 'user' role and is_active=True internally (disallows public escalation).
    5. Persists the new User and handles database IntegrityError/SQLAlchemyError with rollbacks.
    """
    normalized_email = user_data.email

    # Check for existing user with identical email
    existing_user = db.scalars(
        select(User).where(User.email == normalized_email)
    ).first()

    if existing_user is not None:
        raise UserAlreadyExistsError("A user with this email already exists.")

    # Securely hash password using Argon2id
    hashed_password = hash_password(user_data.password)

    # Instantiate User model with strictly controlled server-side defaults
    new_user = User(
        name=user_data.name,
        email=normalized_email,
        password_hash=hashed_password,
        role=UserRole.USER.value,
        is_active=True,
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Handle race condition where another request registered this email concurrently
        logger.warning("Uniqueness conflict during user registration for email")
        raise UserAlreadyExistsError("A user with this email already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure during user creation: %s", type(exc).__name__)
        raise AuthServiceError("An internal database error occurred while creating user.") from exc

    db.refresh(new_user)
    return new_user
