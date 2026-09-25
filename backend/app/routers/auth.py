from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.session import get_db
from app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import (
    AuthServiceError,
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
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


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain access token",
    description="Authenticates user credentials and returns a signed JWT access token.",
)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Public login endpoint.
    Accepts email and password.
    Returns JWT access token on success.
    Returns 401 Unauthorized for invalid email or password.
    Returns 403 Forbidden if user account is inactive.
    """
    try:
        user = authenticate_user(db=db, credentials=credentials)
        access_token = create_access_token(user_id=user.id)
        return TokenResponse(access_token=access_token, token_type="bearer")
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )
