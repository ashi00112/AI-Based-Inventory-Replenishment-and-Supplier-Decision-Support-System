import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import UserRegister, UserLogin

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


class InvalidCredentialsError(Exception):
    """
    Domain exception raised when authentication credentials (email or password) are invalid.
    Prevents user enumeration by mapping both unknown email and bad password to the same error.
    """
    pass


class InactiveUserError(Exception):
    """
    Domain exception raised when an inactive user attempts to authenticate.
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


def authenticate_user(db: Session, credentials: UserLogin) -> User:
    """
    Authenticates a user using email and password credentials.

    1. Uses normalized email from UserLogin.
    2. Queries user by email.
    3. Verifies password using verify_password() against the stored Argon2 hash.
    4. Rejects inactive accounts.
    5. Returns authenticated User instance.

    Raises:
    - InvalidCredentialsError: on unknown email or wrong password.
    - InactiveUserError: when is_active is False.
    """
    normalized_email = credentials.email

    user = db.scalars(
        select(User).where(User.email == normalized_email)
    ).first()

    if user is None:
        raise InvalidCredentialsError("Invalid email or password.")

    if not verify_password(credentials.password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password.")

    if not user.is_active:
        raise InactiveUserError("User account is inactive.")

    return user
