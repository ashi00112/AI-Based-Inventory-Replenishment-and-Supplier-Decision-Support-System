"""
User management service supporting administrative RBAC operations.
Enforces that:
- Passwords are securely hashed with Argon2id before storage
- Plaintext passwords and hashes are never leaked
- Duplicate emails are rejected safely
- Roles are strictly validated (ADMIN or STAFF)
- Inactive users are rejected from authentication
"""

import logging
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import AdminUserCreate, AdminUserUpdate
from app.services.auth_service import AuthServiceError, UserAlreadyExistsError

logger = logging.getLogger(__name__)


class UserNotFoundError(Exception):
    """Raised when a referenced user ID does not exist in the database."""
    pass


class InvalidUserOperationError(Exception):
    """Raised when an operation would violate safety rules (e.g. self-deactivation)."""
    pass


def list_users(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Tuple[List[User], int]:
    """
    Returns a paginated list of users and the total count.
    """
    query = select(User)

    if role:
        norm_role = role.strip().lower()
        if norm_role == "staff":
            query = query.where(User.role.in_([UserRole.STAFF.value, UserRole.USER.value]))
        else:
            query = query.where(User.role == norm_role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0

    items_query = query.order_by(User.id.asc()).offset(skip).limit(limit)
    items = list(db.scalars(items_query).all())

    return items, total


def get_user_by_id(db: Session, user_id: int) -> User:
    """
    Retrieves a single user by primary key.
    Raises UserNotFoundError if absent.
    """
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(f"User with ID {user_id} was not found.")
    return user


def admin_create_user(db: Session, user_in: AdminUserCreate) -> User:
    """
    Creates a new user account initiated by an Administrator.
    Validates email uniqueness and hashes password.
    """
    normalized_email = user_in.email.strip().lower()

    # Pre-check for duplicate email
    existing = db.scalars(select(User).where(User.email == normalized_email)).first()
    if existing is not None:
        raise UserAlreadyExistsError("A user with this email address already exists.")

    # Determine role value
    role_input = user_in.role.strip().lower()
    role_value = UserRole.ADMIN.value if role_input == "admin" else UserRole.STAFF.value

    hashed_pw = hash_password(user_in.password)

    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        password_hash=hashed_pw,
        role=role_value,
        is_active=True,
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("A user with this email address already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure creating user: %s", type(exc).__name__)
        raise AuthServiceError("Database error while creating user.") from exc

    db.refresh(new_user)
    logger.info("Admin created new user '%s' (%s) with role '%s'.", new_user.name, new_user.email, new_user.role)
    return new_user


def admin_update_user(db: Session, user_id: int, user_in: AdminUserUpdate) -> User:
    """
    Updates user account properties (name, email, role, is_active, password).
    """
    user = get_user_by_id(db, user_id)

    if user_in.name is not None:
        user.name = user_in.name.strip()

    if user_in.email is not None:
        norm_email = user_in.email.strip().lower()
        if norm_email != user.email:
            existing = db.scalars(select(User).where(User.email == norm_email)).first()
            if existing is not None:
                raise UserAlreadyExistsError("A user with this email address already exists.")
            user.email = norm_email

    if user_in.role is not None:
        role_input = user_in.role.strip().lower()
        user.role = UserRole.ADMIN.value if role_input == "admin" else UserRole.STAFF.value

    if user_in.is_active is not None:
        user.is_active = user_in.is_active

    if user_in.password is not None:
        user.password_hash = hash_password(user_in.password)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("A user with this email address already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise AuthServiceError("Database error while updating user.") from exc

    db.refresh(user)
    logger.info("Updated user ID %d (%s).", user.id, user.email)
    return user


def deactivate_user(db: Session, user_id: int, current_admin_id: Optional[int] = None) -> User:
    """
    Deactivates a user account (is_active = False).
    Guards against an administrator deactivating their own currently logged-in account.
    """
    if current_admin_id is not None and current_admin_id == user_id:
        raise InvalidUserOperationError("Administrators cannot deactivate their own active account.")

    user = get_user_by_id(db, user_id)
    user.is_active = False

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AuthServiceError("Database error during account deactivation.") from exc

    db.refresh(user)
    logger.info("Deactivated user ID %d (%s).", user.id, user.email)
    return user


def activate_user(db: Session, user_id: int) -> User:
    """
    Reactivates a deactivated user account (is_active = True).
    """
    user = get_user_by_id(db, user_id)
    user.is_active = True

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise AuthServiceError("Database error during account activation.") from exc

    db.refresh(user)
    logger.info("Reactivated user ID %d (%s).", user.id, user.email)
    return user


def ensure_initial_admin(db: Session) -> User:
    """
    Seeds the initial administrator account if no admin user exists in the database.
    Configuration sourced from Settings (INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_PASSWORD).
    """
    admin_user = db.scalars(
        select(User).where(User.role == UserRole.ADMIN.value)
    ).first()

    if admin_user is not None:
        return admin_user

    # No admin exists: create default system admin
    admin_email = getattr(settings, "INITIAL_ADMIN_EMAIL", "admin@smartsupply.ai")
    admin_password = getattr(settings, "INITIAL_ADMIN_PASSWORD", "Admin1234!")
    admin_name = getattr(settings, "INITIAL_ADMIN_NAME", "System Administrator")

    # Check if a user with this email already exists
    existing = db.scalars(select(User).where(User.email == admin_email.lower())).first()
    if existing:
        existing.role = UserRole.ADMIN.value
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    new_admin = User(
        name=admin_name,
        email=admin_email.lower(),
        password_hash=hash_password(admin_password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    logger.info("Initial system administrator seeded: %s", new_admin.email)
    return new_admin
