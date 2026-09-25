import pytest
from fastapi.testclient import TestClient
import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import decode_access_token, hash_password
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User, UserRole


@pytest.fixture(scope="function")
def test_db_session():
    """
    Creates an isolated in-memory SQLite database using StaticPool so multiple
    sessions in the same test function share the in-memory state.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def auth_client(test_db_session):
    """
    TestClient with get_db overridden to use the isolated in-memory test database.
    """
    _, TestingSessionLocal = test_db_session

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def registered_user(test_db_session):
    """
    Pre-seeds an active user in the test database.
    """
    db, _ = test_db_session
    user = User(
        name="Test User",
        email="john@example.com",
        password_hash=hash_password("StrongPassword123!"),
        role=UserRole.USER.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def inactive_user(test_db_session):
    """
    Pre-seeds an inactive user in the test database.
    """
    db, _ = test_db_session
    user = User(
        name="Inactive User",
        email="inactive@example.com",
        password_hash=hash_password("InactivePassword123!"),
        role=UserRole.USER.value,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_valid_login_flow(auth_client: TestClient, registered_user: User):
    """
    1. Valid email + valid password returns 200 OK.
    2. Response contains access_token and token_type == 'bearer'.
    3. Returned token decodes using decode_access_token().
    4. Decoded user ID matches the logged-in user.
    14. Response never contains password or password_hash.
    16. Generated JWT contains no password info.
    """
    payload = {
        "email": "john@example.com",
        "password": "StrongPassword123!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "password" not in data
    assert "password_hash" not in data

    token = data["access_token"]
    payload_decoded = decode_access_token(token)
    assert payload_decoded.user_id == registered_user.id
    assert payload_decoded.sub == str(registered_user.id)
    assert payload_decoded.type == "access"

    # Raw claims inspection ensures no passwords leaked into JWT
    raw_claims = jwt.decode(token, options={"verify_signature": False})
    assert "password" not in raw_claims
    assert "password_hash" not in raw_claims


def test_wrong_password_returns_401_with_www_authenticate(
    auth_client: TestClient, registered_user: User
):
    """
    5. Wrong password returns 401.
    8. 401 response includes WWW-Authenticate: Bearer header.
    """
    payload = {
        "email": "john@example.com",
        "password": "WrongPassword999!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unknown_email_returns_401(auth_client: TestClient):
    """
    6. Unknown email returns 401.
    7. Wrong password and unknown email use the EXACT SAME public error message.
    """
    payload = {
        "email": "unknown.user@example.com",
        "password": "AnyPassword123!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_error_message_identical_for_wrong_password_and_unknown_email(
    auth_client: TestClient, registered_user: User
):
    """
    7. Verifies user enumeration prevention: identical status and message.
    """
    resp_bad_pw = auth_client.post(
        "/api/v1/auth/login",
        json={"email": registered_user.email, "password": "WrongPassword!"},
    )
    resp_bad_email = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "WrongPassword!"},
    )

    assert resp_bad_pw.status_code == resp_bad_email.status_code == 401
    assert resp_bad_pw.json() == resp_bad_email.json() == {"detail": "Invalid email or password."}


def test_inactive_user_returns_403_forbidden(
    auth_client: TestClient, inactive_user: User
):
    """
    9. Inactive user returns 403 Forbidden.
    """
    payload = {
        "email": "inactive@example.com",
        "password": "InactivePassword123!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive."


def test_case_insensitive_email_login_normalization(
    auth_client: TestClient, registered_user: User
):
    """
    10. Email normalization: registered as 'john@example.com', login as '  JOHN@EXAMPLE.COM  ' succeeds.
    """
    payload = {
        "email": "  JOHN@EXAMPLE.COM  ",
        "password": "StrongPassword123!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    token_claims = decode_access_token(data["access_token"])
    assert token_claims.user_id == registered_user.id


def test_invalid_email_format_returns_422(auth_client: TestClient):
    """
    11. Invalid email format returns 422 Unprocessable Entity.
    """
    payload = {
        "email": "not-a-valid-email",
        "password": "ValidPassword123!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422


def test_missing_password_returns_422(auth_client: TestClient):
    """
    12. Missing password field returns 422.
    """
    payload = {
        "email": "john@example.com",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422


def test_empty_password_returns_422(auth_client: TestClient):
    """
    13. Empty password returns 422.
    """
    payload = {
        "email": "john@example.com",
        "password": "",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422


def test_login_does_not_alter_user_attributes(
    auth_client: TestClient, registered_user: User, test_db_session
):
    """
    15. Login does not alter role, is_active, or password_hash.
    """
    db, _ = test_db_session
    orig_role = registered_user.role
    orig_active = registered_user.is_active
    orig_hash = registered_user.password_hash

    payload = {
        "email": registered_user.email,
        "password": "StrongPassword123!",
    }
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    db.expire_all()
    reloaded_user = db.scalars(select(User).where(User.id == registered_user.id)).first()
    assert reloaded_user is not None
    assert reloaded_user.role == orig_role
    assert reloaded_user.is_active == orig_active
    assert reloaded_user.password_hash == orig_hash
