from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User
from app.schemas.auth import UserRegister
from app.services.auth_service import AuthServiceError, UserAlreadyExistsError, create_user


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


@pytest.fixture(autouse=True)
def enable_registration_for_tests(monkeypatch):
    """Enables registration endpoint during isolated unit testing of the registration flow."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", True)


def test_valid_registration_flow(auth_client: TestClient, test_db_session):
    """
    1. Valid registration returns 201 Created.
    2. Response includes public fields: id, name, email, role, is_active, created_at, updated_at.
    3. Response does NOT include password or password_hash.
    4. User is persisted in the database.
    5. Stored password_hash is not equal to password and verifies with verify_password.
    6. Role is always 'user'.
    7. is_active is always True.
    """
    db, _ = test_db_session
    payload = {
        "name": "John Silva",
        "email": "john@example.com",
        "password": "StrongPassword123!",
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["name"] == "John Silva"
    assert data["email"] == "john@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data

    # Verify no credentials leaked in API response
    assert "password" not in data
    assert "password_hash" not in data

    # Verify persistence in database
    persisted_user = db.scalars(
        select(User).where(User.email == "john@example.com")
    ).first()
    assert persisted_user is not None
    assert persisted_user.id == data["id"]
    assert persisted_user.name == "John Silva"
    assert persisted_user.role == "user"
    assert persisted_user.is_active is True

    # Verify password hash security
    assert persisted_user.password_hash != "StrongPassword123!"
    assert verify_password("StrongPassword123!", persisted_user.password_hash) is True


def test_duplicate_email_returns_409_conflict(auth_client: TestClient):
    """
    Verify duplicate email registration returns 409 Conflict with clear error detail.
    """
    payload = {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "password": "Password1234!",
    }

    # First registration succeeds
    resp1 = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Duplicate registration fails with 409
    resp2 = auth_client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["detail"] == "A user with this email already exists."


def test_case_insensitive_duplicate_email_prevention(auth_client: TestClient):
    """
    Verify case-varied and whitespace-padded duplicate emails are rejected.
    JOHN@EXAMPLE.COM and john@example.com must not create two accounts.
    """
    payload1 = {
        "name": "User One",
        "email": "john@example.com",
        "password": "Password1234!",
    }
    resp1 = auth_client.post("/api/v1/auth/register", json=payload1)
    assert resp1.status_code == 201

    payload2 = {
        "name": "User Two",
        "email": "  JOHN@EXAMPLE.COM  ",
        "password": "Password1234!",
    }
    resp2 = auth_client.post("/api/v1/auth/register", json=payload2)
    assert resp2.status_code == 409
    assert resp2.json()["detail"] == "A user with this email already exists."


def test_invalid_email_format_returns_422(auth_client: TestClient):
    """
    Verify improperly formatted emails fail request validation with 422 Unprocessable Entity.
    """
    payload = {
        "name": "Invalid Email",
        "email": "not-a-valid-email",
        "password": "Password1234!",
    }
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_password_shorter_than_minimum_returns_422(auth_client: TestClient):
    """
    Verify passwords shorter than 8 characters fail validation with 422.
    """
    payload = {
        "name": "Short Password",
        "email": "short@example.com",
        "password": "short",
    }
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_attempt_to_submit_role_admin_returns_422(auth_client: TestClient):
    """
    Verify callers cannot escalate privileges by supplying 'role' in request body.
    """
    payload = {
        "name": "Attacker",
        "email": "attacker@example.com",
        "password": "Password1234!",
        "role": "admin",
    }
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_attempt_to_submit_is_active_returns_422(auth_client: TestClient):
    """
    Verify callers cannot alter account activation status in request body.
    """
    payload = {
        "name": "Attacker",
        "email": "status@example.com",
        "password": "Password1234!",
        "is_active": False,
    }
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_attempt_to_submit_password_hash_returns_422(auth_client: TestClient):
    """
    Verify callers cannot inject a raw password_hash field.
    """
    payload = {
        "name": "Attacker",
        "email": "hashinject@example.com",
        "password": "Password1234!",
        "password_hash": "$argon2id$fake",
    }
    response = auth_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_database_integrity_error_triggers_rollback(test_db_session):
    """
    Verify that an IntegrityError during session commit triggers rollback
    and converts safely to UserAlreadyExistsError without leaking DB errors.
    """
    db, _ = test_db_session
    user_data = UserRegister(
        name="Rollback Test",
        email="rollback@example.com",
        password="ValidPassword123!",
    )

    with patch.object(db, "commit", side_effect=IntegrityError("mock statement", {}, None)):
        with patch.object(db, "rollback") as mock_rollback:
            with pytest.raises(UserAlreadyExistsError):
                create_user(db=db, user_data=user_data)
            mock_rollback.assert_called_once()


def test_unexpected_database_error_triggers_rollback(test_db_session):
    """
    Verify that unexpected SQLAlchemyError triggers rollback and raises AuthServiceError.
    """
    db, _ = test_db_session
    user_data = UserRegister(
        name="DB Error Test",
        email="dberror@example.com",
        password="ValidPassword123!",
    )

    with patch.object(db, "commit", side_effect=OperationalError("mock operational error", {}, None)):
        with patch.object(db, "rollback") as mock_rollback:
            with pytest.raises(AuthServiceError):
                create_user(db=db, user_data=user_data)
            mock_rollback.assert_called_once()
