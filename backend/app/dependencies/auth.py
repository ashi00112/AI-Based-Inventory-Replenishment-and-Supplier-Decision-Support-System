"""
Bearer-token authentication dependency for SmartSupply AI.

Extracts and validates the JWT access token from the Authorization header,
loads the corresponding User from the database, and enforces that the
account is still active.

Security rules:
- The database User record is the source of truth for role, is_active, etc.
- Never trust browser-supplied role, user ID outside the validated JWT, or email.
- Never log complete JWT tokens.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.database.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# HTTPBearer extracts "Authorization: Bearer <token>" automatically.
# auto_error=False prevents automatic 403 on missing credentials,
# allowing us to return 401 with standard WWW-Authenticate: Bearer header.
_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)

_INACTIVE_USER_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="User account is inactive.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that returns the authenticated User ORM object.

    Flow:
    1. Extract Bearer token from the Authorization header.
    2. Decode and validate the JWT using decode_access_token().
    3. Obtain the validated user ID from the token subject.
    4. Query User from the database using SQLAlchemy Session.
    5. Ensure the user still exists.
    6. Ensure user.is_active is True.
    7. Return the User ORM object.

    On any failure, returns 401 Unauthorized with WWW-Authenticate: Bearer.
    """
    # 1. Missing Authorization header
    if credentials is None:
        raise _CREDENTIALS_ERROR

    token = credentials.credentials

    # 2–3. Decode and validate JWT
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise _CREDENTIALS_ERROR

    user_id = payload.user_id

    # 4–5. Load user from database (database is single source of truth)
    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR

    # 6. Ensure account is active
    if not user.is_active:
        raise _INACTIVE_USER_ERROR

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extracts authenticated user if Bearer token is provided, or None if absent.
    Raises 401 if credentials are provided but invalid or if user is inactive.
    """
    if credentials is None:
        return None
    return get_current_user(credentials=credentials, db=db)


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    RBAC dependency requiring ADMIN role.
    Raises 403 Forbidden if the authenticated user is not an administrator.
    """
    role_str = (current_user.role or "").strip().lower()
    if role_str != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required.",
        )
    return current_user


def require_staff_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    RBAC dependency requiring either STAFF or ADMIN role.
    Raises 403 Forbidden if user role is unrecognized or unauthorized.
    """
    role_str = (current_user.role or "").strip().lower()
    allowed = {"admin", "staff", "user"}
    if role_str not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Staff or Admin role required.",
        )
    return current_user


def require_catalog_access(
    current_user: User = Depends(require_staff_or_admin),
) -> User:
    """
    Catalog and supplier access dependency.
    STAFF and ADMIN have access.
    Anonymous requests receive 401; unrecognized roles receive 403.
    """
    return current_user


def require_roles(*allowed_roles: str):
    """
    Factory creating a dependency that verifies the user possesses one of the specified roles.
    """
    normalized_allowed = {r.strip().lower() for r in allowed_roles}
    if "staff" in normalized_allowed:
        normalized_allowed.add("user")

    def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").strip().lower()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires one of the following roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return _role_checker
