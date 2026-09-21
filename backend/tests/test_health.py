from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """
    Test root endpoint returns welcome message and navigation links.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data
    assert "health" in data
    assert data["api_version"] == "/api/v1"


def test_health_endpoint(client: TestClient):
    """
    Test GET /health returns proper diagnostic payload.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["ok", "degraded"]
    assert "environment" in data
    assert "project_name" in data
    assert "database_connected" in data
    assert isinstance(data["database_connected"], bool)
    assert "timestamp" in data


def test_api_v1_health_endpoint(client: TestClient):
    """
    Test GET /api/v1/health (versioned health endpoint).
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database_connected" in data
