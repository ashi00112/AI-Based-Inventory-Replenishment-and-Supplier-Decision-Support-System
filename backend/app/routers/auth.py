from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
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
    Disabled for internal enterprise deployment.
    Returns 403 Forbidden unless ALLOW_PUBLIC_REGISTRATION is explicitly enabled.
    """
    if not getattr(settings, "ALLOW_PUBLIC_REGISTRATION", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Contact system administrator for account creation.",
        )

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


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
    description="Returns the profile of the currently authenticated user based on the Bearer token.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Protected endpoint — requires a valid Bearer token.
    Returns the current user's public profile (never password or password_hash).
    """
    return current_user

