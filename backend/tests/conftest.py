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
