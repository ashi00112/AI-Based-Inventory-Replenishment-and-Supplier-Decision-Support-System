from datetime import datetime, timedelta, timezone
import pytest
import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    InvalidTokenError,
)
from app.schemas.auth import TokenPayload


def test_create_access_token_returns_non_empty_string():
    """1. create_access_token() returns a valid, non-empty JWT string."""
    token = create_access_token(user_id=42)
    assert isinstance(token, str)
    assert len(token) > 0
    # Standard compact JWT has 3 parts separated by dots
    assert len(token.split(".")) == 3


def test_valid_token_decodes_successfully():
    """2. A valid token can be decoded successfully into TokenPayload."""
    token = create_access_token(user_id=101)
    payload = decode_access_token(token)
    assert isinstance(payload, TokenPayload)


def test_decoded_sub_corresponds_to_original_user_id():
    """3. Decoded sub and user_id correspond to the original user ID."""
    user_id = 999
    token = create_access_token(user_id=user_id)
    payload = decode_access_token(token)
    assert payload.sub == "999"
    assert payload.user_id == 999
    assert payload["sub"] == "999"
    assert payload["user_id"] == 999


def test_token_type_is_access():
    """4. Token type is strictly 'access'."""
    token = create_access_token(user_id=7)
    payload = decode_access_token(token)
    assert payload.type == "access"


def test_token_contains_issued_at_information():
    """5. Token contains issued-at information with timezone awareness."""
    token = create_access_token(user_id=12)
    payload = decode_access_token(token)
    assert payload.iat is not None
    assert isinstance(payload.iat, datetime)
    assert payload.iat.tzinfo is not None


def test_token_contains_expiration_information():
    """6. Token contains expiration information with timezone awareness."""
    token = create_access_token(user_id=15)
    payload = decode_access_token(token)
    assert payload.exp is not None
    assert isinstance(payload.exp, datetime)
    assert payload.exp.tzinfo is not None


def test_expiration_occurs_after_issued_at():
    """7. Expiration occurs strictly after issued-at timestamp."""
    token = create_access_token(user_id=23)
    payload = decode_access_token(token)
    assert payload.exp > payload.iat


def test_expiration_duration_matches_configured_lifetime():
    """8. Expiration duration approximately matches configured lifetime (30 minutes)."""
    token = create_access_token(user_id=55)
    payload = decode_access_token(token)
    diff = (payload.exp - payload.iat).total_seconds()
    expected_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert abs(diff - expected_seconds) < 5


@pytest.mark.parametrize(
    "malformed_token",
    [
        "not.a.valid.jwt",
        "invalid_token_string",
        "",
        "   ",
        "header.payload",
    ],
)
def test_malformed_token_rejected_safely(malformed_token: str):
    """9. Malformed token strings are rejected safely with InvalidTokenError."""
    with pytest.raises(InvalidTokenError):
        decode_access_token(malformed_token)


def test_token_with_tampered_signature_is_rejected():
    """10. Token with modified/tampered signature is rejected."""
    token = create_access_token(user_id=88)
    tampered_token = token[:-5] + "XXXXX"
    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered_token)


def test_expired_token_is_rejected():
    """11. Expired token is rejected with InvalidTokenError."""
    past_delta = timedelta(minutes=-10)
    expired_token = create_access_token(user_id=99, expires_delta=past_delta)
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(expired_token)
    assert "expired" in str(exc_info.value).lower()


def test_token_missing_sub_is_rejected():
    """12. Token missing 'sub' claim is rejected."""
    now = datetime.now(timezone.utc)
    raw_payload = {
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(
        raw_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(token)
    assert "subject" in str(exc_info.value).lower() or "sub" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()


def test_token_with_wrong_type_is_rejected():
    """13. Token with non-access type (e.g. 'refresh') is rejected."""
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": "123",
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(
        raw_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(token)
    assert "type" in str(exc_info.value).lower()


def test_token_with_non_numeric_user_id_is_rejected():
    """14. Token with non-numeric subject is rejected."""
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": "not_an_integer_id",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(
        raw_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(token)
    assert "numeric" in str(exc_info.value).lower() or "user id" in str(exc_info.value).lower()


def test_jwt_payload_never_contains_password_or_hash():
    """15. JWT payload never contains password or password_hash claims."""
    token = create_access_token(user_id=77)
    # Decode unverified to inspect raw claims
    raw_claims = jwt.decode(token, options={"verify_signature": False})

    assert "password" not in raw_claims
    assert "password_hash" not in raw_claims
    # Verify only intended minimal claims are present
    assert set(raw_claims.keys()) == {"sub", "type", "iat", "exp"}
