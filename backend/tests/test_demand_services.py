






from datetime import date, timedelta
import pytest

from app.schemas.demand import DailyDemandPoint, DailyForecastPoint, DemandDataPoint
from app.services.demand_forecasting import (
    analyze_historical_demand,
    calculate_expected_demand,
    calculate_forecast_metrics,
    calculate_stockout_risk,
    evaluate_moving_average_forecast,
    evaluate_weekday_seasonal_forecast,
    generate_moving_average_forecast,
    generate_weekday_seasonal_forecast,
    preprocess_demand_data,
    select_best_forecast_model,
)


def test_empty_dataset_rejection():
    """1. Empty historical dataset is rejected with ValueError."""
    with pytest.raises(ValueError, match="Historical demand dataset cannot be empty"):
        preprocess_demand_data([])

    with pytest.raises(ValueError, match="Cleaned demand series cannot be empty"):
        analyze_historical_demand([])


def test_chronological_sorting():
    """2. Out-of-order date observations are sorted chronologically."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 5), quantity=50.0),
        DemandDataPoint(date=date(2026, 1, 1), quantity=10.0),
        DemandDataPoint(date=date(2026, 1, 3), quantity=30.0),
    ]
    cleaned = preprocess_demand_data(raw_data)

    assert len(cleaned) == 5
    assert cleaned[0].date == date(2026, 1, 1)
    assert cleaned[1].date == date(2026, 1, 2)
    assert cleaned[2].date == date(2026, 1, 3)
    assert cleaned[3].date == date(2026, 1, 4)
    assert cleaned[4].date == date(2026, 1, 5)


def test_duplicate_date_aggregation():
    """3. Multiple observations for the same calendar date are summed."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=10.0),
        DemandDataPoint(date=date(2026, 1, 1), quantity=5.0),
        DemandDataPoint(date=date(2026, 1, 1), quantity=15.0),
    ]
    cleaned = preprocess_demand_data(raw_data)

    assert len(cleaned) == 1
    assert cleaned[0].date == date(2026, 1, 1)
    assert cleaned[0].quantity == 30.0


def test_missing_date_filling_with_zero():
    """4. Gaps in calendar dates are filled with quantity 0.0."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=10.0),
        DemandDataPoint(date=date(2026, 1, 4), quantity=20.0),
    ]
    cleaned = preprocess_demand_data(raw_data)

    assert len(cleaned) == 4
    assert cleaned[0].quantity == 10.0
    assert cleaned[1].quantity == 0.0  # 2026-01-02
    assert cleaned[2].quantity == 0.0  # 2026-01-03
    assert cleaned[3].quantity == 20.0  # 2026-01-04


def test_correct_total_demand():
    """5. Total demand calculation correctly sums quantities."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=10.0),
        DemandDataPoint(date=date(2026, 1, 2), quantity=25.0),
        DemandDataPoint(date=date(2026, 1, 3), quantity=15.0),
    ]
    cleaned = preprocess_demand_data(raw_data)
    analysis = analyze_historical_demand(cleaned)

    assert analysis.total_demand == 50.0
    assert analysis.number_of_days == 3


def test_correct_average_demand():
    """6. Average daily demand calculation computes the mean across all days including zero-demand days."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=10.0),
        DemandDataPoint(date=date(2026, 1, 3), quantity=20.0),
    ]
    cleaned = preprocess_demand_data(raw_data)  # Days: [10, 0, 20] -> Total 30 over 3 days
    analysis = analyze_historical_demand(cleaned)

    assert analysis.total_demand == 30.0
    assert analysis.number_of_days == 3
    assert analysis.average_daily_demand == 10.0


def test_correct_min_max_demand():
    """7. Min and max demand accurately reflect extreme daily values in series."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=5.0),
        DemandDataPoint(date=date(2026, 1, 2), quantity=100.0),
        DemandDataPoint(date=date(2026, 1, 4), quantity=50.0),
    ]
    cleaned = preprocess_demand_data(raw_data)  # Series: [5, 100, 0, 50]
    analysis = analyze_historical_demand(cleaned)

    assert analysis.minimum_daily_demand == 0.0
    assert analysis.maximum_daily_demand == 100.0


def test_correct_standard_deviation_behavior():
    """8. Standard deviation computes sample std dev (ddof=1) for multi-day series."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=10.0),
        DemandDataPoint(date=date(2026, 1, 2), quantity=20.0),
        DemandDataPoint(date=date(2026, 1, 3), quantity=30.0),
    ]
    cleaned = preprocess_demand_data(raw_data)
    analysis = analyze_historical_demand(cleaned)

    # Values: [10, 20, 30], mean = 20, sample std dev = 10.0
    assert analysis.demand_std_dev == 10.0


def test_single_day_dataset():
    """9. Single-day series reports std_dev = 0.0 and matching total, avg, min, and max."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=42.0),
    ]
    cleaned = preprocess_demand_data(raw_data)
    analysis = analyze_historical_demand(cleaned)

    assert analysis.number_of_days == 1
    assert analysis.total_demand == 42.0
    assert analysis.average_daily_demand == 42.0
    assert analysis.minimum_daily_demand == 42.0
    assert analysis.maximum_daily_demand == 42.0
    assert analysis.demand_std_dev == 0.0


def test_zero_demand_observations():
    """10. Zero-demand observations are handled cleanly without error."""
    raw_data = [
        DemandDataPoint(date=date(2026, 1, 1), quantity=0.0),
        DemandDataPoint(date=date(2026, 1, 2), quantity=0.0),
    ]
    cleaned = preprocess_demand_data(raw_data)
    analysis = analyze_historical_demand(cleaned)

    assert analysis.number_of_days == 2
    assert analysis.total_demand == 0.0
    assert analysis.average_daily_demand == 0.0
    assert analysis.minimum_daily_demand == 0.0
    assert analysis.maximum_daily_demand == 0.0
    assert analysis.demand_std_dev == 0.0


# =====================================================================
# MILESTONE 3 TESTS — DEMAND FORECASTING (SIMPLE MOVING AVERAGE)
# =====================================================================


def test_forecast_horizon_length_and_dates():
    """11. Forecast generates exact horizon length starting 1 calendar day after history."""
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=20.0),
        DailyDemandPoint(date=date(2026, 1, 3), quantity=30.0),
    ]
    forecasts = generate_moving_average_forecast(cleaned_history, forecast_horizon_days=5)

    assert len(forecasts) == 5
    assert forecasts[0].date == date(2026, 1, 4)
    assert forecasts[1].date == date(2026, 1, 5)
    assert forecasts[2].date == date(2026, 1, 6)
    assert forecasts[3].date == date(2026, 1, 7)
    assert forecasts[4].date == date(2026, 1, 8)


def test_sma_numerical_accuracy():
    """12. SMA computes arithmetic mean of last window_size observations."""
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=20.0),
        DailyDemandPoint(date=date(2026, 1, 3), quantity=30.0),
        DailyDemandPoint(date=date(2026, 1, 4), quantity=40.0),
        DailyDemandPoint(date=date(2026, 1, 5), quantity=50.0),
    ]
    # Window = 3 -> Uses last 3: [30, 40, 50] -> Mean = 40.0
    forecasts = generate_moving_average_forecast(cleaned_history, forecast_horizon_days=3, window_size=3)

    assert len(forecasts) == 3
    for pt in forecasts:
        assert pt.forecasted_quantity == 40.0


def test_short_history_adaptation():
    """13. Window automatically adapts to use all available observations if history < window_size."""
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=20.0),
    ]
    # Window = 7, History = 2 -> Effective window = 2 -> Mean = (10+20)/2 = 15.0
    forecasts = generate_moving_average_forecast(cleaned_history, forecast_horizon_days=2, window_size=7)

    assert len(forecasts) == 2
    assert forecasts[0].forecasted_quantity == 15.0
    assert forecasts[1].forecasted_quantity == 15.0


def test_single_day_history_forecast():
    """14. Single-day history produces a constant forecast equal to that day's value."""
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=25.0),
    ]
    forecasts = generate_moving_average_forecast(cleaned_history, forecast_horizon_days=3, window_size=7)

    assert len(forecasts) == 3
    for pt in forecasts:
        assert pt.forecasted_quantity == 25.0


def test_all_zero_demand_forecast():
    """15. All-zero demand history yields constant 0.0 forecast quantities."""
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=0.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=0.0),
        DailyDemandPoint(date=date(2026, 1, 3), quantity=0.0),
        DailyDemandPoint(date=date(2026, 1, 4), quantity=0.0),
    ]
    forecasts = generate_moving_average_forecast(cleaned_history, forecast_horizon_days=4)

    assert len(forecasts) == 4
    for pt in forecasts:
        assert pt.forecasted_quantity == 0.0


def test_empty_history_forecast_rejection():
    """16. Empty cleaned history is rejected with ValueError."""
    with pytest.raises(ValueError, match="Cleaned demand series cannot be empty"):
        generate_moving_average_forecast([], forecast_horizon_days=5)


def test_forecast_horizon_zero_rejection():
    """17. forecast_horizon_days = 0 is rejected with ValueError."""
    cleaned_history = [DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0)]
    with pytest.raises(ValueError, match="Forecast horizon days must be greater than 0"):
        generate_moving_average_forecast(cleaned_history, forecast_horizon_days=0)


def test_negative_forecast_horizon_rejection():
    """18. Negative forecast_horizon_days is rejected with ValueError."""
    cleaned_history = [DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0)]
    with pytest.raises(ValueError, match="Forecast horizon days must be greater than 0"):
        generate_moving_average_forecast(cleaned_history, forecast_horizon_days=-5)


def test_window_size_zero_rejection():
    """19. window_size = 0 is rejected with ValueError."""
    cleaned_history = [DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0)]
    with pytest.raises(ValueError, match="Window size must be greater than 0"):
        generate_moving_average_forecast(cleaned_history, forecast_horizon_days=5, window_size=0)


def test_negative_window_size_rejection():
    """20. Negative window_size is rejected with ValueError."""
    cleaned_history = [DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0)]
    with pytest.raises(ValueError, match="Window size must be greater than 0"):
        generate_moving_average_forecast(cleaned_history, forecast_horizon_days=5, window_size=-3)


def test_forecast_quantities_satisfy_schema_contract():
    """21. All generated DailyForecastPoint objects satisfy non-negative Pydantic contract."""
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.5),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=0.0),
    ]
    forecasts = generate_moving_average_forecast(cleaned_history, forecast_horizon_days=2)

    for f in forecasts:
        assert f.forecasted_quantity >= 0.0
        assert f.confidence_interval_lower is None
        assert f.confidence_interval_upper is None


# =====================================================================
# MILESTONE 4 TESTS — FORECAST EVALUATION & BACKTESTING
# =====================================================================


def test_calculate_forecast_metrics_manual_example():
    """22. Verifies MAE, RMSE, and MAPE against standard manual calculations."""
    actuals = [10.0, 20.0, 30.0]
    preds = [12.0, 18.0, 33.0]
    metrics = calculate_forecast_metrics(actuals, preds, model_name="Simple Moving Average")

    assert metrics.mae == 2.3333
    assert metrics.rmse == 2.3805
    assert metrics.mape == 13.3333
    assert metrics.selected_model == "Simple Moving Average"


def test_perfect_forecast_metrics():
    """23. Perfect forecast produces MAE = 0, RMSE = 0, MAPE = 0."""
    actuals = [10.0, 20.0, 30.0]
    preds = [10.0, 20.0, 30.0]
    metrics = calculate_forecast_metrics(actuals, preds)

    assert metrics.mae == 0.0
    assert metrics.rmse == 0.0
    assert metrics.mape == 0.0


def test_some_zero_actual_values_mape():
    """24. MAE and RMSE use all observations while MAPE excludes actual == 0.0."""
    actuals = [0.0, 10.0, 20.0]
    preds = [5.0, 12.0, 18.0]
    metrics = calculate_forecast_metrics(actuals, preds)

    # MAE = (5 + 2 + 2) / 3 = 3.0
    assert metrics.mae == 3.0
    # RMSE = sqrt((25 + 4 + 4) / 3) = sqrt(11) = 3.3166
    assert metrics.rmse == 3.3166
    # MAPE excludes actual=0 -> uses [10, 20]: (2/10 + 2/20)/2 * 100 = 15.0%
    assert metrics.mape == 15.0


def test_all_zero_actual_values_raises_value_error():
    """25. All-zero actuals raises ValueError because MAPE is undefined."""
    actuals = [0.0, 0.0, 0.0]
    preds = [1.0, 2.0, 3.0]
    with pytest.raises(ValueError, match="MAPE is undefined when all actual values are zero"):
        calculate_forecast_metrics(actuals, preds)


def test_mismatched_actual_predicted_lengths_rejection():
    """26. Mismatched array lengths are rejected with ValueError."""
    with pytest.raises(ValueError, match="must have equal length"):
        calculate_forecast_metrics([10.0, 20.0], [10.0])


def test_empty_series_metrics_rejection():
    """27. Empty actual/predicted series are rejected with ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        calculate_forecast_metrics([], [])


def test_negative_actual_value_rejection():
    """28. Negative actual values are rejected with ValueError."""
    with pytest.raises(ValueError, match="Actual values cannot be negative"):
        calculate_forecast_metrics([-5.0, 10.0], [5.0, 10.0])


def test_negative_predicted_value_rejection():
    """29. Negative predicted values are rejected with ValueError."""
    with pytest.raises(ValueError, match="Predicted values cannot be negative"):
        calculate_forecast_metrics([5.0, 10.0], [-5.0, 10.0])


def test_empty_or_whitespace_model_name_rejection():
    """30. Empty or whitespace-only model names are rejected with ValueError."""
    with pytest.raises(ValueError, match="Model name cannot be empty"):
        calculate_forecast_metrics([10.0], [10.0], model_name="   ")


def test_evaluate_sma_invalid_validation_days_zero_or_negative():
    """31. validation_days <= 0 is rejected with ValueError."""
    history = [DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0)]
    with pytest.raises(ValueError, match="Validation days must be greater than 0"):
        evaluate_moving_average_forecast(history, validation_days=0)

    with pytest.raises(ValueError, match="Validation days must be greater than 0"):
        evaluate_moving_average_forecast(history, validation_days=-2)


def test_evaluate_sma_validation_days_greater_or_equal_history():
    """32. validation_days >= len(cleaned_data) is rejected with ValueError."""
    history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=20.0),
    ]
    with pytest.raises(ValueError, match="Historical data length must be greater than validation_days"):
        evaluate_moving_average_forecast(history, validation_days=2)


def test_evaluate_sma_invalid_window_size():
    """33. window_size <= 0 in evaluate_moving_average_forecast is rejected with ValueError."""
    history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=20.0),
    ]
    with pytest.raises(ValueError, match="Window size must be greater than 0"):
        evaluate_moving_average_forecast(history, validation_days=1, window_size=0)


def test_deterministic_sma_holdout_evaluation():
    """34. End-to-end SMA holdout evaluation on synthetic chronological series."""
    # 10 days total: training (first 7) = [10.0]*7 -> SMA = 10.0. Validation (last 3) = [20.0]*3.
    history = [DailyDemandPoint(date=date(2026, 1, i), quantity=10.0) for i in range(1, 8)] + [
        DailyDemandPoint(date=date(2026, 1, i), quantity=20.0) for i in range(8, 11)
    ]
    metrics = evaluate_moving_average_forecast(history, validation_days=3, window_size=7)

    # Actuals: [20, 20, 20], Preds: [10, 10, 10] -> MAE = 10.0, RMSE = 10.0, MAPE = 50.0%
    assert metrics.mae == 10.0
    assert metrics.rmse == 10.0
    assert metrics.mape == 50.0
    assert metrics.selected_model == "Simple Moving Average"


def test_no_data_leakage_behavior():
    """35. Proves validation actuals do not leak into training forecast calculation."""
    # Training (first 7 days): [10.0]*7 -> SMA = 10.0. Validation (last 3 days): [100.0]*3.
    history = [DailyDemandPoint(date=date(2026, 1, i), quantity=10.0) for i in range(1, 8)] + [
        DailyDemandPoint(date=date(2026, 1, i), quantity=100.0) for i in range(8, 11)
    ]
    metrics = evaluate_moving_average_forecast(history, validation_days=3, window_size=7)

    # If leakage occurred (e.g. including validation in SMA), forecast would be > 10.0 and error < 90.0
    # MAE must equal |100 - 10| = 90.0
    assert metrics.mae == 90.0


# =====================================================================
# MILESTONE 5 TESTS — EXPECTED FUTURE DEMAND CALCULATION
# =====================================================================


def test_basic_expected_demand():
    """36. Sums daily forecasted quantities accurately."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 1, 1), forecasted_quantity=10.0),
        DailyForecastPoint(date=date(2026, 1, 2), forecasted_quantity=20.0),
        DailyForecastPoint(date=date(2026, 1, 3), forecasted_quantity=30.0),
    ]
    total = calculate_expected_demand(forecasts)
    assert total == 60.0


def test_single_forecast_day_expected_demand():
    """37. Single-day forecast list returns that day's quantity."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 1, 1), forecasted_quantity=25.0),
    ]
    total = calculate_expected_demand(forecasts)
    assert total == 25.0


def test_all_zero_forecasts_expected_demand():
    """38. All-zero forecast quantities yield expected demand of 0.0."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 1, 1), forecasted_quantity=0.0),
        DailyForecastPoint(date=date(2026, 1, 2), forecasted_quantity=0.0),
        DailyForecastPoint(date=date(2026, 1, 3), forecasted_quantity=0.0),
    ]
    total = calculate_expected_demand(forecasts)
    assert total == 0.0


def test_fractional_forecast_quantities_expected_demand():
    """39. Fractional quantities sum correctly and round to 4 decimal places."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 1, 1), forecasted_quantity=10.5),
        DailyForecastPoint(date=date(2026, 1, 2), forecasted_quantity=20.25),
        DailyForecastPoint(date=date(2026, 1, 3), forecasted_quantity=5.25),
    ]
    total = calculate_expected_demand(forecasts)
    assert total == 36.0


def test_empty_forecast_list_expected_demand_rejection():
    """40. Empty forecast list raises ValueError."""
    with pytest.raises(ValueError, match="Forecast points list cannot be empty"):
        calculate_expected_demand([])


def test_input_forecast_points_immutability():
    """41. Input DailyForecastPoint instances are not mutated."""
    pt1 = DailyForecastPoint(date=date(2026, 1, 1), forecasted_quantity=15.0)
    pt2 = DailyForecastPoint(date=date(2026, 1, 2), forecasted_quantity=25.0)
    forecasts = [pt1, pt2]

    calculate_expected_demand(forecasts)

    assert pt1.date == date(2026, 1, 1)
    assert pt1.forecasted_quantity == 15.0
    assert pt2.date == date(2026, 1, 2)
    assert pt2.forecasted_quantity == 25.0


def test_confidence_intervals_ignored_in_expected_demand():
    """42. Confidence interval upper and lower bounds do not alter expected demand total."""
    forecasts = [
        DailyForecastPoint(
            date=date(2026, 1, 1),
            forecasted_quantity=10.0,
            confidence_interval_lower=5.0,
            confidence_interval_upper=15.0,
        ),
    ]
    total = calculate_expected_demand(forecasts)
    assert total == 10.0


def test_sma_to_expected_demand_pipeline():
    """43. End-to-end pipeline: history -> SMA forecast -> expected demand."""
    history = [
        DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0),
        DailyDemandPoint(date=date(2026, 1, 2), quantity=20.0),
        DailyDemandPoint(date=date(2026, 1, 3), quantity=30.0),
    ]
    # SMA window = 3 -> mean = 20.0. Horizon = 2 days -> [20.0, 20.0] -> Total = 40.0
    forecasts = generate_moving_average_forecast(history, forecast_horizon_days=2, window_size=3)
    total = calculate_expected_demand(forecasts)

    assert total == 40.0


# =====================================================================
# MILESTONE 6 TESTS — STOCK-OUT RISK ANALYSIS
# =====================================================================


def test_stockout_risk_high_insufficient_stock():
    """44. S < D yields HIGH risk."""
    risk = calculate_stockout_risk(current_available_stock=20.0, expected_demand_over_lead_time=30.0)
    assert risk.risk_level == "HIGH"
    assert risk.current_available_stock == 20
    assert risk.expected_demand_over_lead_time == 30.0


def test_stockout_risk_high_zero_stock_positive_demand():
    """45. Zero stock with positive demand yields HIGH risk."""
    risk = calculate_stockout_risk(current_available_stock=0.0, expected_demand_over_lead_time=30.0)
    assert risk.risk_level == "HIGH"
    assert risk.current_available_stock == 0
    assert risk.expected_demand_over_lead_time == 30.0


def test_stockout_risk_medium_exact_coverage():
    """46. S == D yields MEDIUM risk."""
    risk = calculate_stockout_risk(current_available_stock=30.0, expected_demand_over_lead_time=30.0)
    assert risk.risk_level == "MEDIUM"
    assert risk.current_available_stock == 30
    assert risk.expected_demand_over_lead_time == 30.0


def test_stockout_risk_medium_limited_buffer():
    """47. D < S < 1.5*D yields MEDIUM risk."""
    risk = calculate_stockout_risk(current_available_stock=40.0, expected_demand_over_lead_time=30.0)
    assert risk.risk_level == "MEDIUM"
    assert risk.current_available_stock == 40
    assert risk.expected_demand_over_lead_time == 30.0


def test_stockout_risk_medium_exact_upper_boundary():
    """48. S == 1.5*D yields MEDIUM risk."""
    risk = calculate_stockout_risk(current_available_stock=45.0, expected_demand_over_lead_time=30.0)
    assert risk.risk_level == "MEDIUM"
    assert risk.current_available_stock == 45
    assert risk.expected_demand_over_lead_time == 30.0


def test_stockout_risk_low_above_threshold():
    """49. S > 1.5*D yields LOW risk."""
    risk = calculate_stockout_risk(current_available_stock=46.0, expected_demand_over_lead_time=30.0)
    assert risk.risk_level == "LOW"
    assert risk.current_available_stock == 46
    assert risk.expected_demand_over_lead_time == 30.0


def test_stockout_risk_low_zero_demand_zero_stock():
    """50. Zero demand and zero stock yields LOW risk."""
    risk = calculate_stockout_risk(current_available_stock=0.0, expected_demand_over_lead_time=0.0)
    assert risk.risk_level == "LOW"
    assert risk.current_available_stock == 0
    assert risk.expected_demand_over_lead_time == 0.0


def test_stockout_risk_low_zero_demand_positive_stock():
    """51. Zero demand and positive stock yields LOW risk."""
    risk = calculate_stockout_risk(current_available_stock=50.0, expected_demand_over_lead_time=0.0)
    assert risk.risk_level == "LOW"
    assert risk.current_available_stock == 50
    assert risk.expected_demand_over_lead_time == 0.0


def test_stockout_risk_negative_stock_rejection():
    """52. Negative available stock raises ValueError."""
    with pytest.raises(ValueError, match="Current available stock cannot be negative"):
        calculate_stockout_risk(current_available_stock=-1.0, expected_demand_over_lead_time=30.0)


def test_stockout_risk_negative_demand_rejection():
    """53. Negative expected demand raises ValueError."""
    with pytest.raises(ValueError, match="Expected demand over lead time cannot be negative"):
        calculate_stockout_risk(current_available_stock=30.0, expected_demand_over_lead_time=-1.0)


def test_stockout_risk_fractional_expected_demand():
    """54. Fractional expected demand preserves fractional float value in output."""
    risk = calculate_stockout_risk(current_available_stock=30.0, expected_demand_over_lead_time=30.5)
    assert risk.risk_level == "HIGH"
    assert risk.current_available_stock == 30
    assert risk.expected_demand_over_lead_time == 30.5


def test_stockout_risk_determinism():
    """55. Multiple calls with identical parameters return identical results."""
    r1 = calculate_stockout_risk(current_available_stock=40.0, expected_demand_over_lead_time=30.0)
    r2 = calculate_stockout_risk(current_available_stock=40.0, expected_demand_over_lead_time=30.0)

    assert r1.risk_level == r2.risk_level
    assert r1.current_available_stock == r2.current_available_stock
    assert r1.expected_demand_over_lead_time == r2.expected_demand_over_lead_time


# =====================================================================
# MILESTONE 9 TESTS — SEASONAL FORECASTING & MODEL SELECTION
# =====================================================================


def test_generate_weekday_seasonal_forecast_pattern():
    """56. Weekday seasonal forecast uses historical observations of matching weekdays."""
    # 28 days total (4 full weeks): Mon Jan 5 2026 to Sun Feb 1 2026
    # Mondays (Jan 5, 12, 19, 26) have demand 10.0
    # Other days (Tue-Sun) have demand 50.0
    cleaned_history = []
    for i in range(28):
        current_date = date(2026, 1, 5) + timedelta(days=i)
        qty = 10.0 if current_date.weekday() == 0 else 50.0
        cleaned_history.append(DailyDemandPoint(date=current_date, quantity=qty))

    # Forecast 7 days into future (Mon Feb 2 to Sun Feb 8 2026)
    forecasts = generate_weekday_seasonal_forecast(cleaned_history, forecast_horizon_days=7)

    assert len(forecasts) == 7
    assert forecasts[0].date == date(2026, 2, 2)  # Monday
    assert forecasts[0].forecasted_quantity == 10.0  # Monday average
    assert forecasts[1].date == date(2026, 2, 3)  # Tuesday
    assert forecasts[1].forecasted_quantity == 50.0  # Tuesday average
    assert forecasts[5].date == date(2026, 2, 7)  # Saturday
    assert forecasts[5].forecasted_quantity == 50.0  # Saturday average


def test_generate_weekday_seasonal_forecast_lookback_limit():
    """57. Weekday seasonal forecast respects seasonal_lookback_weeks limit (averages at most N recent same-weekdays)."""
    # 10 weeks of history (70 days)
    # Mondays in weeks 1-2 (Jan 5, Jan 12): demand 100.0
    # Mondays in weeks 3-10 (Jan 19 through Mar 9): demand 10.0
    cleaned_history = []
    start = date(2026, 1, 5)
    for i in range(70):
        current_date = start + timedelta(days=i)
        if current_date.weekday() == 0:
            qty = 100.0 if i < 14 else 10.0
        else:
            qty = 20.0
        cleaned_history.append(DailyDemandPoint(date=current_date, quantity=qty))

    # Lookback = 8 -> uses last 8 Mondays (weeks 3-10, all 10.0) -> mean = 10.0
    forecasts = generate_weekday_seasonal_forecast(
        cleaned_history,
        forecast_horizon_days=7,
        seasonal_lookback_weeks=8,
    )

    assert forecasts[0].forecasted_quantity == 10.0


def test_generate_weekday_seasonal_forecast_fallback_to_sma():
    """58. Fallback to SMA occurs when fewer than 2 same-weekday observations exist."""
    # 3 days history (Mon, Tue, Wed)
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, 5), quantity=10.0),  # Mon
        DailyDemandPoint(date=date(2026, 1, 6), quantity=20.0),  # Tue
        DailyDemandPoint(date=date(2026, 1, 7), quantity=30.0),  # Wed
    ]
    # Forecast 3 days (Thu, Fri, Sat) -> each has 0 historical observations (< 2)
    # Fallback to SMA average of 3 days: (10 + 20 + 30) / 3 = 20.0
    forecasts = generate_weekday_seasonal_forecast(cleaned_history, forecast_horizon_days=3)

    assert len(forecasts) == 3
    for f in forecasts:
        assert f.forecasted_quantity == 20.0


def test_generate_weekday_seasonal_forecast_invalid_inputs():
    """59. Rejects empty history, non-positive horizon, and non-positive lookback."""
    history = [DailyDemandPoint(date=date(2026, 1, 1), quantity=10.0)]

    with pytest.raises(ValueError, match="Cleaned demand series cannot be empty"):
        generate_weekday_seasonal_forecast([], forecast_horizon_days=5)

    with pytest.raises(ValueError, match="Forecast horizon days must be greater than 0"):
        generate_weekday_seasonal_forecast(history, forecast_horizon_days=0)

    with pytest.raises(ValueError, match="Seasonal lookback weeks must be greater than 0"):
        generate_weekday_seasonal_forecast(history, forecast_horizon_days=5, seasonal_lookback_weeks=0)


def test_evaluate_weekday_seasonal_forecast_holdout():
    """60. Evaluates weekday seasonal model using deterministic 14-day holdout split."""
    # 28 days total (4 weeks): training = first 14 days, validation = last 14 days
    # Mon=10.0, Tue-Sun=50.0 pattern across full history
    cleaned_history = []
    for i in range(28):
        current_date = date(2026, 1, 5) + timedelta(days=i)
        qty = 10.0 if current_date.weekday() == 0 else 50.0
        cleaned_history.append(DailyDemandPoint(date=current_date, quantity=qty))

    metrics = evaluate_weekday_seasonal_forecast(cleaned_history, validation_days=14)

    assert metrics.selected_model == "Weekday Seasonal Moving Average"
    assert metrics.mae == 0.0
    assert metrics.rmse == 0.0
    assert metrics.mape == 0.0


def test_evaluate_weekday_seasonal_forecast_invalid_inputs():
    """61. Rejects invalid validation_days and short history in seasonal evaluation."""
    history = [DailyDemandPoint(date=date(2026, 1, i), quantity=10.0) for i in range(1, 10)]

    with pytest.raises(ValueError, match="Validation days must be greater than 0"):
        evaluate_weekday_seasonal_forecast(history, validation_days=0)

    with pytest.raises(ValueError, match="Historical data length must be greater than validation_days"):
        evaluate_weekday_seasonal_forecast(history, validation_days=14)


def test_select_best_forecast_model_seasonal_selected():
    """62. Selects Weekday Seasonal Moving Average when its holdout MAE is lower than SMA MAE."""
    # Strong weekly pattern over 28 days: Mon=10, Tue-Sun=50
    cleaned_history = []
    for i in range(28):
        current_date = date(2026, 1, 5) + timedelta(days=i)
        qty = 10.0 if current_date.weekday() == 0 else 50.0
        cleaned_history.append(DailyDemandPoint(date=current_date, quantity=qty))

    # Holdout validation (last 14 days):
    # Weekday seasonal captures exact Mon vs Tue-Sun pattern -> MAE = 0.0
    # SMA 7-day averages across Mon+Tue-Sun -> SMA MAE > 0.0
    best_metrics = select_best_forecast_model(cleaned_history, validation_days=14)

    assert best_metrics.selected_model == "Weekday Seasonal Moving Average"
    assert best_metrics.mae == 0.0


def test_select_best_forecast_model_sma_selected():
    """63. Selects Simple Moving Average when SMA holdout MAE is lower than Weekday Seasonal MAE."""
    # 28 days with a recent sharp step increase:
    # Days 1-21 = 10.0, Days 22-28 = 50.0
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, i), quantity=10.0 if i <= 21 else 50.0)
        for i in range(1, 29)
    ]

    # SMA (7-day window) adapts quickly to recent 50.0 level
    # Weekday seasonal lookback averages historical same-weekdays (10.0 from earlier weeks), underperforming
    best_metrics = select_best_forecast_model(cleaned_history, validation_days=14)

    assert best_metrics.selected_model == "Simple Moving Average"


def test_select_best_forecast_model_tie_selects_sma():
    """64. Tie-breaking rule selects Simple Moving Average when both models have equal MAE."""
    # 28 days of perfectly flat constant demand = 20.0
    cleaned_history = [
        DailyDemandPoint(date=date(2026, 1, i), quantity=20.0) for i in range(1, 29)
    ]

    # Both models achieve MAE = 0.0 -> exact tie selects SMA
    best_metrics = select_best_forecast_model(cleaned_history, validation_days=14)

    assert best_metrics.selected_model == "Simple Moving Average"
    assert best_metrics.mae == 0.0


# --- Milestone 11: Projected Stock Trajectory & Stock-out Date Tests ---

from app.services.demand_forecasting import calculate_projected_stock_trajectory


def test_calculate_projected_stock_trajectory_no_stockout_ending_zero():
    """65. Stock ending at exactly zero is satisfied and is NOT a stock-out."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, i), forecasted_quantity=10.0)
        for i in range(1, 4)
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(30, forecasts)

    assert [pt.projected_stock for pt in enriched] == [20.0, 10.0, 0.0]
    assert stockout_date is None


def test_calculate_projected_stock_trajectory_stockout_midway():
    """66. Projected stock-out is detected on the first day projected_stock becomes negative."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, i), forecasted_quantity=10.0)
        for i in range(1, 4)
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(25, forecasts)

    assert [pt.projected_stock for pt in enriched] == [15.0, 5.0, -5.0]
    assert stockout_date == date(2026, 2, 3)


def test_calculate_projected_stock_trajectory_zero_starting_stock():
    """67. Zero starting stock with positive demand causes stock-out on day 1."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, i), forecasted_quantity=10.0)
        for i in range(1, 3)
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(0, forecasts)

    assert [pt.projected_stock for pt in enriched] == [-10.0, -20.0]
    assert stockout_date == date(2026, 2, 1)


def test_calculate_projected_stock_trajectory_all_zero_forecast():
    """68. All-zero forecast demand maintains constant projected stock and returns None stockout_date."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, i), forecasted_quantity=0.0)
        for i in range(1, 4)
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(20, forecasts)

    assert [pt.projected_stock for pt in enriched] == [20.0, 20.0, 20.0]
    assert stockout_date is None


def test_calculate_projected_stock_trajectory_fractional_and_4decimal():
    """69. Fractional forecast quantities round projected stock deterministically to 4 decimal places."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, i), forecasted_quantity=3.3333)
        for i in range(1, 4)
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(10, forecasts)

    assert [pt.projected_stock for pt in enriched] == [6.6667, 3.3334, 0.0001]
    assert stockout_date is None


def test_calculate_projected_stock_trajectory_first_stockout_date_preserved():
    """70. First stock-out date remains the first date even as deficit deepens on subsequent days."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, 1), forecasted_quantity=15.0),
        DailyForecastPoint(date=date(2026, 2, 2), forecasted_quantity=20.0),
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(10, forecasts)

    assert [pt.projected_stock for pt in enriched] == [-5.0, -25.0]
    assert stockout_date == date(2026, 2, 1)


def test_calculate_projected_stock_trajectory_no_stockout_returns_none():
    """71. Sufficient stock across full horizon returns None for projected_stockout_date."""
    forecasts = [
        DailyForecastPoint(date=date(2026, 2, i), forecasted_quantity=10.0)
        for i in range(1, 4)
    ]
    enriched, stockout_date = calculate_projected_stock_trajectory(100, forecasts)

    assert [pt.projected_stock for pt in enriched] == [90.0, 80.0, 70.0]
    assert stockout_date is None


def test_calculate_projected_stock_trajectory_invalid_inputs():
    """72. Rejects negative stock or empty daily forecast list."""
    forecasts = [DailyForecastPoint(date=date(2026, 2, 1), forecasted_quantity=10.0)]

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_projected_stock_trajectory(-5, forecasts)

    with pytest.raises(ValueError, match="cannot be empty"):
        calculate_projected_stock_trajectory(10, [])
