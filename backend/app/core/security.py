from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings
from app.schemas.auth import TokenPayload


class InvalidTokenError(Exception):
    """
    Domain exception raised when a JWT token is invalid, expired, tampered, or malformed.
    Prevents leaking internal library exceptions to API callers.
    """
    pass


# Configure pwdlib with Argon2 password hashing algorithm
_password_hasher = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """
    Hash a plain-text password using the Argon2 algorithm.

    Argon2id is a memory-hard password hashing algorithm designed to resist
    GPU-based brute-force cracking attacks.
    """
    if not isinstance(password, str):
        raise TypeError("Password must be a string.")
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Safely compare a user's entered plain-text password with the stored Argon2 hash.

    Returns True if valid, False otherwise. Malformed or invalid hash inputs
    are handled gracefully and return False without raising unhandled exceptions.
    """
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        return False
    if not plain_password or not hashed_password:
        return False
    try:
        return _password_hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a signed JWT access token for the given user ID.

    Claims:
    - sub: string representation of user ID
    - type: 'access'
    - iat: UTC issuance timestamp
    - exp: UTC expiration timestamp based on JWT_ACCESS_TOKEN_EXPIRE_MINUTES or expires_delta
    """
    if not isinstance(user_id, int):
        raise TypeError("user_id must be an integer.")

    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> TokenPayload:
    """
    Validate and decode a JWT access token.

    Validates:
    1. Signature integrity using configured JWT_SECRET_KEY and JWT_ALGORITHM.
    2. Expiration timeframe (rejects expired tokens).
    3. Required claims ('sub', 'type', 'iat', 'exp').
    4. Token type is strictly 'access'.
    5. Subject claim represents a valid numeric user ID.

    Returns a validated TokenPayload instance.
    Raises InvalidTokenError on any failure.
    """
    if not isinstance(token, str) or not token.strip():
        raise InvalidTokenError("Token string is missing or empty.")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired.") from exc
    except jwt.MissingRequiredClaimError as exc:
        raise InvalidTokenError(f"Token is missing required claim: {exc.claim}.") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid token.") from exc

    except Exception as exc:
        raise InvalidTokenError("Could not validate token.") from exc

    # Validate token type claim
    if payload.get("type") != "access":
        raise InvalidTokenError("Invalid token type.")

    # Validate subject claim
    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token is missing subject.")
    try:
        int(sub)
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError("Token subject must represent a valid numeric user ID.") from exc

    iat_val = payload["iat"]
    exp_val = payload["exp"]
    iat_dt = (
        datetime.fromtimestamp(iat_val, tz=timezone.utc)
        if isinstance(iat_val, (int, float))
        else iat_val
    )
    exp_dt = (
        datetime.fromtimestamp(exp_val, tz=timezone.utc)
        if isinstance(exp_val, (int, float))
        else exp_val
    )

    return TokenPayload(
        sub=str(sub),
        type=payload["type"],
        iat=iat_dt,
        exp=exp_dt,
    )
