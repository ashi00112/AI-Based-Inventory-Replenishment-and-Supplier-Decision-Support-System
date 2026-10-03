
from datetime import date, timedelta
import pytest

from app.agents.demand.agent import DemandRiskAgent
from app.schemas.demand import DemandDataPoint


def get_sample_historical_data(num_days: int = 20) -> list:
    """Helper function to generate sample historical demand observations."""
    return [
        {"date": date(2026, 1, i), "quantity": 10.0 if i % 2 == 1 else 20.0}
        for i in range(1, num_days + 1)
    ]


def test_full_successful_pipeline():
    """1. Agent runs full pipeline and returns structured dictionary matching DemandAgentOutput."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 10,
        "lead_time_days": 3,
        "current_available_stock": 50,
    }
    output = agent.run(context)

    assert isinstance(output, dict)
    assert output["product_id"] == 1
    assert output["forecast_horizon_days"] == 10
    assert len(output["daily_forecasts"]) == 10
    assert "evaluation_metrics" in output
    assert "stockout_risk" in output
    assert output["stockout_risk"]["current_available_stock"] == 50


def test_product_id_preserved():
    """2. product_id in output matches input context."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 42,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 100,
    }
    output = agent.run(context)
    assert output["product_id"] == 42


def test_daily_forecasts_count():
    """3. len(daily_forecasts) strictly equals forecast_horizon_days."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 14,
        "lead_time_days": 5,
        "current_available_stock": 100,
    }
    output = agent.run(context)
    assert len(output["daily_forecasts"]) == 14


def test_total_forecasted_demand():
    """4. total_forecasted_demand matches the exact sum across daily_forecasts."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 100,
    }
    output = agent.run(context)
    manual_sum = sum(pt["forecasted_quantity"] for pt in output["daily_forecasts"])
    assert round(output["total_forecasted_demand"], 4) == round(manual_sum, 4)


def test_lead_time_demand_in_stockout():
    """5. stockout_risk.expected_demand_over_lead_time equals the sum of the first lead_time_days forecast quantities."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 10,
        "lead_time_days": 4,
        "current_available_stock": 100,
    }
    output = agent.run(context)
    manual_lead_time_sum = sum(pt["forecasted_quantity"] for pt in output["daily_forecasts"][:4])
    assert round(output["stockout_risk"]["expected_demand_over_lead_time"], 4) == round(manual_lead_time_sum, 4)


def test_high_risk_propagation():
    """6. Stock less than expected demand over lead time yields HIGH risk."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 10,
        "lead_time_days": 3,
        "current_available_stock": 10,  # Expected demand is ~45 (3 * 15)
    }
    output = agent.run(context)
    assert output["stockout_risk"]["risk_level"] == "HIGH"


def test_medium_risk_propagation():
    """7. Stock equal to expected demand over lead time yields MEDIUM risk."""
    agent = DemandRiskAgent()
    # 20 days of constant 10.0 demand -> forecast = 10.0
    history = [DemandDataPoint(date=date(2026, 1, i), quantity=10.0) for i in range(1, 21)]
    context = {
        "product_id": 1,
        "historical_data": history,
        "forecast_horizon_days": 5,
        "lead_time_days": 3,
        "current_available_stock": 30,  # 3 days * 10.0 = 30.0 expected demand
    }
    output = agent.run(context)
    assert output["stockout_risk"]["risk_level"] == "MEDIUM"


def test_low_risk_propagation():
    """8. Stock exceeding 1.5x expected demand over lead time yields LOW risk."""
    agent = DemandRiskAgent()
    history = [DemandDataPoint(date=date(2026, 1, i), quantity=10.0) for i in range(1, 21)]
    context = {
        "product_id": 1,
        "historical_data": history,
        "forecast_horizon_days": 5,
        "lead_time_days": 3,
        "current_available_stock": 100,  # 100 > 1.5 * 30.0
    }
    output = agent.run(context)
    assert output["stockout_risk"]["risk_level"] == "LOW"


def test_evaluation_metrics_included():
    """9. evaluation_metrics in output contains mae, rmse, mape, and selected_model."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    output = agent.run(context)
    metrics = output["evaluation_metrics"]
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "mape" in metrics
    assert metrics["selected_model"] in [
        "Simple Moving Average",
        "Weekday Seasonal Moving Average",
    ]


def test_missing_product_id_rejection():
    """10. Missing product_id raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="Missing required context parameter: product_id"):
        agent.run(context)


def test_missing_historical_data_rejection():
    """11. Missing historical_data raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="Missing required context parameter: historical_data"):
        agent.run(context)


def test_missing_forecast_horizon_days_rejection():
    """12. Missing forecast_horizon_days raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="Missing required context parameter: forecast_horizon_days"):
        agent.run(context)


def test_missing_lead_time_days_rejection():
    """13. Missing lead_time_days raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="Missing required context parameter: lead_time_days"):
        agent.run(context)


def test_missing_current_available_stock_rejection():
    """14. Missing current_available_stock raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
    }
    with pytest.raises(ValueError, match="Missing required context parameter: current_available_stock"):
        agent.run(context)


def test_empty_historical_data_rejection():
    """15. Empty historical_data list raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": [],
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="historical_data must be a non-empty list"):
        agent.run(context)


def test_invalid_product_id_rejection():
    """16. product_id <= 0 raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 0,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="product_id must be a positive integer greater than 0"):
        agent.run(context)


def test_invalid_forecast_horizon_days_rejection():
    """17. forecast_horizon_days <= 0 raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 0,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="forecast_horizon_days must be a positive integer greater than 0"):
        agent.run(context)


def test_invalid_lead_time_days_rejection():
    """18. lead_time_days <= 0 raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": -1,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="lead_time_days must be a positive integer greater than 0"):
        agent.run(context)


def test_lead_time_exceeds_horizon_rejection():
    """19. lead_time_days > forecast_horizon_days raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 10,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="lead_time_days cannot exceed forecast_horizon_days"):
        agent.run(context)


def test_negative_current_available_stock_rejection():
    """20. Negative current_available_stock raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": -10,
    }
    with pytest.raises(ValueError, match="current_available_stock cannot be negative"):
        agent.run(context)


def test_fractional_current_available_stock_rejection():
    """21. Fractional current_available_stock float is rejected with ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 30.6,
    }
    with pytest.raises(ValueError, match="current_available_stock must be an integer, not a float"):
        agent.run(context)


def test_insufficient_cleaned_history_for_evaluation():
    """22. Historical data length <= VALIDATION_DAYS (14) raises ValueError."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(10),  # 10 days <= 14
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    with pytest.raises(ValueError, match="Historical data length \\(10\\) must be greater than validation_days \\(14\\)"):
        agent.run(context)


def test_input_historical_data_not_mutated():
    """23. Original input historical_data list and dictionaries are not mutated."""
    agent = DemandRiskAgent()
    history = get_sample_historical_data(20)
    history_copy = [dict(item) for item in history]

    context = {
        "product_id": 1,
        "historical_data": history,
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    agent.run(context)

    assert history == history_copy


def test_repeated_execution_determinism():
    """24. Repeated runs with identical context produce identical outputs."""
    agent = DemandRiskAgent()
    context = {
        "product_id": 1,
        "historical_data": get_sample_historical_data(20),
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 50,
    }
    out1 = agent.run(context)
    out2 = agent.run(context)

    assert out1 == out2


def test_agent_selects_weekday_seasonal_model():
    """25. DemandRiskAgent selects Weekday Seasonal Moving Average when seasonal pattern exists."""
    agent = DemandRiskAgent()
    # 28 days with strong Monday pattern (Mon=10, Tue-Sun=50)
    history = [
        {"date": date(2026, 1, 5) + timedelta(days=i), "quantity": 10.0 if (date(2026, 1, 5) + timedelta(days=i)).weekday() == 0 else 50.0}
        for i in range(28)
    ]
    context = {
        "product_id": 1,
        "historical_data": history,
        "forecast_horizon_days": 7,
        "lead_time_days": 3,
        "current_available_stock": 100,
    }
    output = agent.run(context)

    assert output["evaluation_metrics"]["selected_model"] == "Weekday Seasonal Moving Average"
    assert output["evaluation_metrics"]["mae"] == 0.0


def test_agent_selects_sma_model():
    """26. DemandRiskAgent selects Simple Moving Average when SMA yields lower error."""
    agent = DemandRiskAgent()
    # 28 days of flat demand
    history = [
        {"date": date(2026, 1, i), "quantity": 25.0}
        for i in range(1, 29)
    ]
    context = {
        "product_id": 1,
        "historical_data": history,
        "forecast_horizon_days": 7,
        "lead_time_days": 3,
        "current_available_stock": 100,
    }
    output = agent.run(context)

    # Tie selects SMA
    assert output["evaluation_metrics"]["selected_model"] == "Simple Moving Average"


def test_agent_output_includes_m11_projected_stock_and_stockout_date():
    """27. DemandRiskAgent returns projected_stock for each daily forecast and projected_stockout_date in risk metrics."""
    agent = DemandRiskAgent()
    # 20 days history (exceeds 14-day holdout validation requirement)
    history = [
        {"date": date(2026, 1, i), "quantity": 10.0}
        for i in range(1, 21)
    ]
    context = {
        "product_id": 1,
        "historical_data": history,
        "forecast_horizon_days": 5,
        "lead_time_days": 2,
        "current_available_stock": 25,  # 25 - 10 = 15, 15 - 10 = 5, 5 - 10 = -5 (stockout on day 3)
    }
    output = agent.run(context)

    forecasts = output["daily_forecasts"]
    assert len(forecasts) == 5
    assert [f["projected_stock"] for f in forecasts] == [15.0, 5.0, -5.0, -15.0, -25.0]

    risk = output["stockout_risk"]
    assert risk["projected_stockout_date"] == date(2026, 1, 23)  # Day 3 date (2026-01-21 + 3 days)
