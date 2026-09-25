from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth import UserRegister, UserResponse
from app.services.auth_service import (
    UserAlreadyExistsError,
    AuthServiceError,
    create_user,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user account with default 'user' role and Argon2id hashed password.",
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Public registration endpoint.
    Accepts name, email, and password.
    Returns the created user's public profile or 409 Conflict if email is already taken.
    """
    try:
        new_user = create_user(db=db, user_data=user_data)
        return new_user
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except AuthServiceError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing registration.",
        )
