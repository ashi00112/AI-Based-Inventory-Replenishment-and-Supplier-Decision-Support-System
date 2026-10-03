from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app
from app.models.user import User


def get_sample_api_historical_data(num_days: int = 20) -> list:
    """Helper function to construct raw historical data payload for API requests."""
    return [
        {"date": f"2026-09-{i:02d}", "quantity": 10.0 if i % 2 == 1 else 20.0}
        for i in range(1, num_days + 1)
    ]


@pytest.fixture
def auth_client():
    """TestClient fixture with authenticated user dependency override."""
    mock_user = User(
        id=1,
        email="analyst@example.com",
        name="Demand Analyst",
        role="user",
        is_active=True,
    )

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    """TestClient fixture without authentication dependency overrides."""
    with TestClient(app) as test_client:
        yield test_client


def test_api_analyze_demand_success(auth_client: TestClient):
    """1. Valid authenticated request to POST /api/v1/demand/analyze returns 200 OK."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 10,
        "lead_time_days": 3,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1
    assert data["forecast_horizon_days"] == 10
    assert len(data["daily_forecasts"]) == 10
    assert "evaluation_metrics" in data
    assert "stockout_risk" in data
    assert "projected_stockout_date" in data["stockout_risk"]
    assert "projected_stock" in data["daily_forecasts"][0]


def test_api_analyze_demand_unauthenticated(unauth_client: TestClient):
    """2. Unauthenticated request returns 401 Unauthorized."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    response = unauth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 401


def test_api_analyze_demand_product_id_preserved(auth_client: TestClient):
    """3. Response product_id matches request product_id."""
    payload = {
        "product_id": 101,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 20,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["product_id"] == 101


def test_api_analyze_demand_forecast_horizon_days_preserved(auth_client: TestClient):
    """4. Response forecast_horizon_days matches request forecast_horizon_days."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 12,
        "lead_time_days": 4,
        "current_available_stock": 20,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["forecast_horizon_days"] == 12


def test_api_analyze_demand_daily_forecasts_count(auth_client: TestClient):
    """5. Output daily_forecasts count equals forecast_horizon_days."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 7,
        "lead_time_days": 3,
        "current_available_stock": 20,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    assert len(response.json()["daily_forecasts"]) == 7


def test_api_analyze_demand_total_forecasted_demand(auth_client: TestClient):
    """6. Output total_forecasted_demand equals sum of daily forecasts."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 20,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    manual_sum = sum(pt["forecasted_quantity"] for pt in data["daily_forecasts"])
    assert round(data["total_forecasted_demand"], 4) == round(manual_sum, 4)


def test_api_analyze_demand_lead_time_demand(auth_client: TestClient):
    """7. Expected demand over lead time equals sum over first lead_time_days forecast points."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 10,
        "lead_time_days": 4,
        "current_available_stock": 20,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    manual_lead_sum = sum(pt["forecasted_quantity"] for pt in data["daily_forecasts"][:4])
    assert round(data["stockout_risk"]["expected_demand_over_lead_time"], 4) == round(manual_lead_sum, 4)


def test_api_analyze_demand_high_risk(auth_client: TestClient):
    """8. Stock less than expected demand over lead time yields HIGH risk."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 10,
        "lead_time_days": 3,
        "current_available_stock": 5,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["stockout_risk"]["risk_level"] == "HIGH"


def test_api_analyze_demand_medium_risk(auth_client: TestClient):
    """9. Stock equal to expected demand over lead time yields MEDIUM risk."""
    constant_history = [
        {"date": f"2026-09-{i:02d}", "quantity": 10.0} for i in range(1, 21)
    ]
    payload = {
        "product_id": 1,
        "historical_data": constant_history,
        "forecast_horizon_days": 5,
        "lead_time_days": 3,
        "current_available_stock": 30,  # 3 days * 10.0 = 30.0
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["stockout_risk"]["risk_level"] == "MEDIUM"


def test_api_analyze_demand_low_risk(auth_client: TestClient):
    """10. Stock exceeding 1.5x expected demand over lead time yields LOW risk."""
    constant_history = [
        {"date": f"2026-09-{i:02d}", "quantity": 10.0} for i in range(1, 21)
    ]
    payload = {
        "product_id": 1,
        "historical_data": constant_history,
        "forecast_horizon_days": 5,
        "lead_time_days": 3,
        "current_available_stock": 100,  # 100 > 1.5 * 30.0
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["stockout_risk"]["risk_level"] == "LOW"


def test_api_analyze_demand_missing_required_field(auth_client: TestClient):
    """11. Request missing product_id returns 422 Unprocessable Entity."""
    payload = {
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_fractional_stock_rejection(auth_client: TestClient):
    """12. Fractional current_available_stock (30.6) returns 422 Unprocessable Entity."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 30.6,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_negative_stock_rejection(auth_client: TestClient):
    """13. Negative current_available_stock returns 422 Unprocessable Entity."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": -5,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_invalid_horizon_rejection(auth_client: TestClient):
    """14. forecast_horizon_days = 0 returns 422 Unprocessable Entity."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 0,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_invalid_lead_time_rejection(auth_client: TestClient):
    """15. lead_time_days = -1 returns 422 Unprocessable Entity."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": -1,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_lead_time_exceeds_horizon(auth_client: TestClient):
    """16. lead_time_days > forecast_horizon_days returns 400 Bad Request."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 10,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 400
    assert "cannot exceed forecast_horizon_days" in response.json()["detail"]


def test_api_analyze_demand_empty_history_rejection(auth_client: TestClient):
    """17. Empty historical_data returns 422 Unprocessable Entity."""
    payload = {
        "product_id": 1,
        "historical_data": [],
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_insufficient_history(auth_client: TestClient):
    """18. History length <= 14 returns 400 Bad Request."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(5),  # 5 days <= 14
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 400
    assert "must be greater than validation_days" in response.json()["detail"]


def test_api_analyze_demand_unexpected_extra_field_rejected(auth_client: TestClient):
    """19. Extra unexpected field in request returns 422 Unprocessable Entity."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
        "unexpected_field": "disallowed",
    }
    response = auth_client.post("/api/v1/demand/analyze", json=payload)
    assert response.status_code == 422


def test_api_analyze_demand_determinism(auth_client: TestClient):
    """20. Repeated identical API requests return identical responses."""
    payload = {
        "product_id": 1,
        "historical_data": get_sample_api_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    res1 = auth_client.post("/api/v1/demand/analyze", json=payload)
    res2 = auth_client.post("/api/v1/demand/analyze", json=payload)

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == res2.json()
