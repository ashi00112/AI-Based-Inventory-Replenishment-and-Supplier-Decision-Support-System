from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.user import User, UserRole
from app.schemas.auth import UserRegister, UserLogin, UserResponse


def test_valid_user_register_succeeds():
    """
    Verify valid registration data initializes UserRegister schema.
    """
    data = {
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "password": "ValidPassword123!",
    }
    schema = UserRegister(**data)
    assert schema.name == "Jane Doe"
    assert schema.email == "jane.doe@example.com"
    assert schema.password == "ValidPassword123!"


def test_invalid_email_is_rejected():
    """
    Verify improperly formatted email strings are rejected.
    """
    invalid_emails = [
        "not-an-email",
        "user@",
        "@domain.com",
        "user@domain",
        "user name@example.com",
    ]
    for email in invalid_emails:
        with pytest.raises(ValidationError):
            UserRegister(
                name="Valid Name",
                email=email,
                password="ValidPassword123!",
            )


def test_password_shorter_than_8_chars_is_rejected():
    """
    Verify passwords with fewer than 8 characters fail validation.
    """
    short_passwords = ["", "1", "1234567", "abcdefg"]
    for pw in short_passwords:
        with pytest.raises(ValidationError):
            UserRegister(
                name="Valid Name",
                email="user@example.com",
                password=pw,
            )


def test_role_cannot_be_supplied_through_user_register():
    """
    Verify public registration rejects 'role' field attempts.
    """
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(
            name="Attempted Admin",
            email="admin.attempt@example.com",
            password="ValidPassword123!",
            role="admin",  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_is_active_cannot_be_supplied_through_user_register():
    """
    Verify public registration rejects 'is_active' field attempts.
    """
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(
            name="Attempted Status Change",
            email="status.attempt@example.com",
            password="ValidPassword123!",
            is_active=False,  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_password_hash_cannot_be_supplied_through_user_register():
    """
    Verify public registration rejects 'password_hash' field attempts.
    """
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(
            name="Attempted Hash Injection",
            email="hash.attempt@example.com",
            password="ValidPassword123!",
            password_hash="$argon2id$fakehash",  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_user_login_validates_expected_fields():
    """
    Verify UserLogin accepts valid credentials and rejects missing/invalid fields.
    """
    # Valid login
    login = UserLogin(email="user@example.com", password="mySecretPassword")
    assert login.email == "user@example.com"
    assert login.password == "mySecretPassword"

    # Invalid email
    with pytest.raises(ValidationError):
        UserLogin(email="invalid_email_format", password="password123")

    # Missing password
    with pytest.raises(ValidationError):
        UserLogin(email="user@example.com", password="")  # empty password fails min_length=1


def test_user_response_from_orm_object():
    """
    Verify UserResponse hydrates correctly from a SQLAlchemy User ORM object.
    """
    now = datetime.now(timezone.utc)
    user_orm = User(
        id=42,
        name="Developer One",
        email="dev.one@example.com",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashvalue",
        role=UserRole.ADMIN.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response_schema = UserResponse.model_validate(user_orm)
    assert response_schema.id == 42
    assert response_schema.name == "Developer One"
    assert response_schema.email == "dev.one@example.com"
    assert response_schema.role == UserRole.ADMIN
    assert response_schema.is_active is True
    assert response_schema.created_at == now
    assert response_schema.updated_at == now


def test_user_response_never_contains_password_or_hash():
    """
    Verify UserResponse schema fields and dumps never expose credentials.
    """
    now = datetime.now(timezone.utc)
    user_orm = User(
        id=1,
        name="Security Sensitive",
        email="sensitive@example.com",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$secret_hash_not_to_leak",
        role=UserRole.USER.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response_schema = UserResponse.model_validate(user_orm)
    dumped = response_schema.model_dump()

    # Verify neither password nor password_hash appear in dumped dictionary
    assert "password" not in dumped
    assert "password_hash" not in dumped

    # Verify neither appears in json string
    json_str = response_schema.model_dump_json()
    assert "password" not in json_str
    assert "password_hash" not in json_str
    assert "secret_hash_not_to_leak" not in json_str


def test_whitespace_and_normalization_behavior():
    """
    Verify names and emails with surrounding whitespace and mixed case normalize properly.
    """
    reg = UserRegister(
        name="   Alice Smith   ",
        email="   ALICE.SMITH@Example.Com   ",
        password="SecurePassword123!",
    )
    assert reg.name == "Alice Smith"
    assert reg.email == "alice.smith@example.com"

    # Whitespace-only name must be rejected
    with pytest.raises(ValidationError):
        UserRegister(
            name="     ",
            email="valid@example.com",
            password="SecurePassword123!",
        )

    # Login email normalization
    login = UserLogin(
        email="   LOGIN.USER@domain.com   ",
        password="myPassword",
    )
    assert login.email == "login.user@domain.com"
