import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.config import settings


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Test client fixture for making requests against the FastAPI app.
    """
    with TestClient(app) as test_client:
        yield test_client


# Legacy catalog CRUD test modules written before RBAC was introduced.
# They test business logic, not auth, so catalog auth is bypassed for them only.
# Real authentication/authorization enforcement is covered by test_rbac.py.
_LEGACY_CATALOG_TEST_MODULES = {
    "test_products",
    "test_suppliers",
    "test_product_suppliers",
    "test_inventory_transactions",
    "test_inventory",
    "test_inventory_monitoring_agent",
}


@pytest.fixture(autouse=True)
def _bypass_catalog_auth_for_legacy_tests(request):
    module_name = request.module.__name__.rsplit(".", 1)[-1]
    if module_name not in _LEGACY_CATALOG_TEST_MODULES:
        yield
        return

    from app.dependencies.auth import require_catalog_access
    from app.models.user import User, UserRole

    def _staff_user() -> User:
        return User(id=0, name="Test Staff", email="staff@example.com",
                    password_hash="x", role=UserRole.STAFF.value, is_active=True)

    app.dependency_overrides[require_catalog_access] = _staff_user
    yield
    app.dependency_overrides.pop(require_catalog_access, None)


@pytest.fixture
def isolated_chroma_dir(tmp_path):
    """Provides a dedicated temporary directory for Chroma storage."""
    chroma_path = tmp_path / "chroma"
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chroma_path


@pytest.fixture(autouse=True)
def isolate_chroma_storage(tmp_path, monkeypatch):
    """
    Global isolation fixture ensuring all test suites run against an isolated
    temporary directory and NEVER touch or mutate the development Chroma store
    at backend/storage/chroma.
    """
    from app.services.chroma_service import reset_chroma_client

    test_chroma = str(tmp_path / "isolated_test_chroma")
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", test_chroma)
    reset_chroma_client()
    yield test_chroma
    reset_chroma_client()
