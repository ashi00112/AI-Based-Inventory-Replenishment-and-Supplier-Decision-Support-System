from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User, UserRole


@pytest.fixture(scope="function")
def test_db_session():
    """
    Creates an isolated in-memory SQLite database using StaticPool.
    Ensures zero interaction with Supabase or any cloud database.
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


def create_test_user(
    db: Session,
    name: str = "Test User",
    email: str = "test@example.com",
    role: str = UserRole.USER.value,
    is_active: bool = True,
    password: str = "SecurePass123!",
) -> User:
    """Helper to insert a user directly into the isolated test database."""
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestAuthMeEndpoint:
    """Comprehensive test suite for GET /api/v1/auth/me and Bearer auth dependency."""

    def test_valid_bearer_token_returns_200(self, auth_client: TestClient, test_db_session):
        """1. Valid Bearer token returns HTTP 200 OK."""
        db, _ = test_db_session
        user = create_test_user(db, name="Alice User", email="alice@example.com")
        token = create_access_token(user_id=user.id)

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_correct_user_is_returned(self, auth_client: TestClient, test_db_session):
        """2. Correct user profile is returned for the given token."""
        db, _ = test_db_session
        user = create_test_user(db, name="Alice Smith", email="alice.smith@example.com")
        token = create_access_token(user_id=user.id)

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        assert data["id"] == user.id
        assert data["name"] == "Alice Smith"
        assert data["email"] == "alice.smith@example.com"
        assert data["is_active"] is True
        assert data["role"] == "user"

    def test_response_contains_expected_public_fields(self, auth_client: TestClient, test_db_session):
        """3. Response contains exactly the expected public fields."""
        db, _ = test_db_session
        user = create_test_user(db, name="Bob Builder", email="bob@example.com")
        token = create_access_token(user_id=user.id)

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        expected_fields = {"id", "name", "email", "role", "is_active", "created_at", "updated_at"}
        assert set(data.keys()) == expected_fields

    def test_password_and_hash_are_never_returned(self, auth_client: TestClient, test_db_session):
        """4. Neither password nor password_hash are present in the response."""
        db, _ = test_db_session
        user = create_test_user(db, name="Secret Agent", email="agent@example.com")
        token = create_access_token(user_id=user.id)

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        assert "password" not in data
        assert "password_hash" not in data
        # Ensure raw response text doesn't leak hash
        assert user.password_hash not in response.text

    def test_missing_authorization_header_returns_401(self, auth_client: TestClient):
        """5. Request without Authorization header returns 401 Unauthorized with WWW-Authenticate."""
        response = auth_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json()["detail"] == "Could not validate credentials."

    def test_invalid_token_returns_401(self, auth_client: TestClient):
        """6. Malformed or invalid JWT token returns 401 Unauthorized."""
        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-valid-token-string"},
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json()["detail"] == "Could not validate credentials."

    def test_expired_token_returns_401(self, auth_client: TestClient, test_db_session):
        """7. Expired token returns 401 Unauthorized."""
        db, _ = test_db_session
        user = create_test_user(db, name="Expired User", email="expired@example.com")
        # Token expired 10 minutes ago
        token = create_access_token(user_id=user.id, expires_delta=timedelta(minutes=-10))

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json()["detail"] == "Could not validate credentials."

    def test_tampered_token_returns_401(self, auth_client: TestClient, test_db_session):
        """8. Token signed with wrong secret key or tampered signature returns 401."""
        db, _ = test_db_session
        user = create_test_user(db, name="Tampered User", email="tampered@example.com")
        # Sign with an incorrect secret
        tampered_token = jwt.encode(
            {"sub": str(user.id), "type": "access"},
            "wrong-secret-key-that-does-not-match",
            algorithm="HS256",
        )

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json()["detail"] == "Could not validate credentials."

    def test_token_referencing_nonexistent_user_returns_401(self, auth_client: TestClient):
        """9. Valid token with subject ID that does not exist in the database returns 401."""
        # Nonexistent user ID 99999
        token = create_access_token(user_id=99999)

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json()["detail"] == "Could not validate credentials."

    def test_inactive_user_cannot_use_auth_me(self, auth_client: TestClient, test_db_session):
        """10. Inactive user cannot access /api/v1/auth/me even with a valid token."""
        db, _ = test_db_session
        inactive_user = create_test_user(
            db,
            name="Deactivated User",
            email="inactive@example.com",
            is_active=False,
        )
        token = create_access_token(user_id=inactive_user.id)

        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json()["detail"] == "User account is inactive."

    def test_user_token_cannot_retrieve_another_users_account(
        self, auth_client: TestClient, test_db_session
    ):
        """11. One user's token cannot retrieve another user's account information."""
        db, _ = test_db_session
        user1 = create_test_user(db, name="User One", email="user1@example.com")
        user2 = create_test_user(db, name="User Two", email="user2@example.com")

        token1 = create_access_token(user_id=user1.id)
        response = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token1}"},
        )
        data = response.json()
        assert data["id"] == user1.id
        assert data["email"] == "user1@example.com"
        assert data["id"] != user2.id
        assert data["email"] != user2.email

    def test_role_comes_from_database_record(self, auth_client: TestClient, test_db_session):
        """12. Role is strictly sourced from current DB User record, reflecting real-time DB changes."""
        db, _ = test_db_session
        user = create_test_user(db, name="Role Test", email="role@example.com", role=UserRole.USER.value)
        token = create_access_token(user_id=user.id)

        # Initial check - role is 'user'
        response1 = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.json()["role"] == "user"

        # Update role in database directly
        user.role = UserRole.ADMIN.value
        db.commit()

        # Subsequent check with the SAME token reflects updated role from database
        response2 = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.json()["role"] == "admin"

    def test_no_cloud_supabase_modified(self, test_db_session):
        """13. Verifies that tests operate strictly in SQLite in-memory without contacting cloud DB."""
        db, _ = test_db_session
        dialect_name = db.bind.dialect.name
        assert dialect_name == "sqlite"
        assert str(db.bind.url) in ("sqlite:///:memory:", "sqlite:///%3Amemory%3A")
