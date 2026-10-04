"""
Admin User Management API Router.
Enforces that only authenticated ADMINISTRATORS can manage user accounts.
STAFF accounts attempting access receive HTTP 403 Forbidden.
Unauthenticated requests receive HTTP 401 Unauthorized.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.user import AdminUserCreate, AdminUserUpdate, UserListResponse
from app.services.auth_service import AuthServiceError, UserAlreadyExistsError
from app.services.user_service import (
    InvalidUserOperationError,
    UserNotFoundError,
    activate_user,
    admin_create_user,
    admin_update_user,
    deactivate_user,
    get_user_by_id,
    list_users,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List users (Admin only)",
    description="Returns a paginated list of system user accounts. Requires ADMIN role.",
)
def get_users(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    role: Optional[str] = Query(None, description="Filter by role: ADMIN or STAFF"),
    is_active: Optional[bool] = Query(None, description="Filter by activation status"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserListResponse:
    items, total = list_users(
        db=db,
        skip=skip,
        limit=limit,
        role=role,
        is_active=is_active,
    )
    return UserListResponse(items=items, total=total)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account (Admin only)",
    description="Creates a new STAFF or ADMIN user account with hashed password. Requires ADMIN role.",
)
def create_new_user(
    user_in: AdminUserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserResponse:
    try:
        new_user = admin_create_user(db=db, user_in=user_in)
        return new_user
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user details by ID (Admin only)",
    description="Retrieves a specific user account details. Requires ADMIN role.",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserResponse:
    try:
        return get_user_by_id(db=db, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user details (Admin only)",
    description="Modifies name, email, role, or active status of a user. Requires ADMIN role.",
)
def update_user(
    user_id: int,
    user_in: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserResponse:
    try:
        return admin_update_user(db=db, user_id=user_id, user_in=user_in)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate user account (Admin only)",
    description="Deactivates a user account, preventing login and token generation. Requires ADMIN role.",
)
def deactivate_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserResponse:
    try:
        return deactivate_user(db=db, user_id=user_id, current_admin_id=current_admin.id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InvalidUserOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate user account (Admin only)",
    description="Reactivates a previously deactivated user account. Requires ADMIN role.",
)
def activate_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserResponse:
    try:
        return activate_user(db=db, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
