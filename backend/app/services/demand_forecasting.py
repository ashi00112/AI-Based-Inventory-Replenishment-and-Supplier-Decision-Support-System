from datetime import date, timedelta
from typing import List
import numpy as np
import pandas as pd

from app.schemas.demand import (
    DailyDemandPoint,
    DailyForecastPoint,
    DemandAnalysis,
    DemandDataPoint,
    EvaluationMetrics,
    StockoutRiskMetrics,
)


def preprocess_demand_data(historical_data: List[DemandDataPoint]) -> List[DailyDemandPoint]:
    """
    Preprocesses raw historical demand observations into a clean, continuous daily series.
    - Rejects empty datasets.
    - Aggregates multiple observations for the same calendar date by summing quantities.
    - Sorts observations chronologically.
    - Fills missing calendar dates between earliest and latest dates with 0.0 demand.
    """
    if not historical_data:
        raise ValueError("Historical demand dataset cannot be empty.")

    # Aggregate demand by date using a dictionary
    date_totals = {}
    for pt in historical_data:
        date_totals[pt.date] = date_totals.get(pt.date, 0.0) + float(pt.quantity)

    min_date = min(date_totals.keys())
    max_date = max(date_totals.keys())

    cleaned_points: List[DailyDemandPoint] = []
    current_date = min_date

    while current_date <= max_date:
        qty = date_totals.get(current_date, 0.0)
        cleaned_points.append(DailyDemandPoint(date=current_date, quantity=round(qty, 4)))
        current_date += timedelta(days=1)

    return cleaned_points


def analyze_historical_demand(cleaned_data: List[DailyDemandPoint]) -> DemandAnalysis:
    """
    Calculates descriptive statistics for a cleaned daily demand time series.
    Calculates total, average, minimum, maximum, sample standard deviation, and count.
    """
    if not cleaned_data:
        raise ValueError("Cleaned demand series cannot be empty.")

    quantities = np.array([pt.quantity for pt in cleaned_data], dtype=float)
    n_days = len(quantities)

    total_demand = float(np.sum(quantities))
    avg_demand = float(np.mean(quantities))
    min_demand = float(np.min(quantities))
    max_demand = float(np.max(quantities))
    
    # Calculate sample standard deviation (ddof=1) if n > 1, else 0.0
    if n_days > 1:
        std_dev = float(np.std(quantities, ddof=1))
    else:
        std_dev = 0.0

    return DemandAnalysis(
        total_demand=round(total_demand, 4),
        average_daily_demand=round(avg_demand, 4),
        minimum_daily_demand=round(min_demand, 4),
        maximum_daily_demand=round(max_demand, 4),
        demand_std_dev=round(std_dev, 4),
        number_of_days=n_days,
    )


def generate_moving_average_forecast(
    cleaned_data: List[DailyDemandPoint],
    forecast_horizon_days: int,
    window_size: int = 7,
) -> List[DailyForecastPoint]:
    """
    Generates a deterministic multi-day demand forecast using Simple Moving Average (SMA).

    Args:
        cleaned_data: Continuous daily demand series from preprocess_demand_data().
        forecast_horizon_days: Number of future days to forecast (must be > 0).
        window_size: Moving average window size in days (default: 7, must be > 0).

    Returns:
        List[DailyForecastPoint] starting on the calendar day immediately after cleaned_data[-1].date.

    Raises:
        ValueError: If cleaned_data is empty or forecast_horizon_days <= 0 or window_size <= 0.
    """
    if not cleaned_data:
        raise ValueError("Cleaned demand series cannot be empty.")
    if forecast_horizon_days <= 0:
        raise ValueError("Forecast horizon days must be greater than 0.")
    if window_size <= 0:
        raise ValueError("Window size must be greater than 0.")

    effective_window = min(window_size, len(cleaned_data))
    recent_points = cleaned_data[-effective_window:]
    sma_value = float(np.mean([pt.quantity for pt in recent_points]))
    sma_value_rounded = round(sma_value, 4)

    last_historical_date = cleaned_data[-1].date
    forecasts: List[DailyForecastPoint] = []

    for day_offset in range(1, forecast_horizon_days + 1):
        future_date = last_historical_date + timedelta(days=day_offset)
        forecasts.append(
            DailyForecastPoint(
                date=future_date,
                forecasted_quantity=sma_value_rounded,
                confidence_interval_lower=None,
                confidence_interval_upper=None,
            )
        )

    return forecasts


def calculate_forecast_metrics(
    actual_values: List[float],
    predicted_values: List[float],
    model_name: str = "Simple Moving Average",
) -> EvaluationMetrics:
    """
    Calculates MAE, RMSE, and MAPE error evaluation metrics given actual and predicted values.

    Args:
        actual_values: Historical observed demand values.
        predicted_values: Model forecasted demand values.
        model_name: Identifier for the model being evaluated.

    Returns:
        EvaluationMetrics schema instance containing rounded mae, rmse, mape, and selected_model.

    Raises:
        ValueError: If arrays are empty, have mismatched lengths, contain negative values,
                    if model_name is blank, or if all actual values are zero (MAPE undefined).
    """
    if not actual_values or not predicted_values:
        raise ValueError("Actual and predicted series cannot be empty.")
    if len(actual_values) != len(predicted_values):
        raise ValueError("Actual and predicted series must have equal length.")
    if not model_name or not model_name.strip():
        raise ValueError("Model name cannot be empty.")

    act_arr = np.array(actual_values, dtype=float)
    pred_arr = np.array(predicted_values, dtype=float)

    if np.any(act_arr < 0.0):
        raise ValueError("Actual values cannot be negative.")
    if np.any(pred_arr < 0.0):
        raise ValueError("Predicted values cannot be negative.")

    # Calculate MAE & RMSE using all observations
    errors = act_arr - pred_arr
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    # Calculate MAPE using only non-zero actual observations
    non_zero_mask = act_arr > 0.0
    if not np.any(non_zero_mask):
        raise ValueError("MAPE is undefined when all actual values are zero.")

    mape = float(np.mean(np.abs(errors[non_zero_mask]) / act_arr[non_zero_mask]) * 100.0)

    return EvaluationMetrics(
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        mape=round(mape, 4),
        selected_model=model_name.strip(),
    )


def evaluate_moving_average_forecast(
    cleaned_data: List[DailyDemandPoint],
    validation_days: int = 7,
    window_size: int = 7,
) -> EvaluationMetrics:
    """
    Evaluates Simple Moving Average (SMA) forecast accuracy using a deterministic historical holdout split.

    Args:
        cleaned_data: Continuous daily demand time series.
        validation_days: Number of trailing historical days to hold out for validation (must be > 0).
        window_size: Moving average window size in days (must be > 0).

    Returns:
        EvaluationMetrics schema instance computed against the held-out validation set.

    Raises:
        ValueError: If cleaned_data is empty, parameters <= 0, or len(cleaned_data) <= validation_days.
    """
    if not cleaned_data:
        raise ValueError("Cleaned demand series cannot be empty.")
    if validation_days <= 0:
        raise ValueError("Validation days must be greater than 0.")
    if window_size <= 0:
        raise ValueError("Window size must be greater than 0.")
    if len(cleaned_data) <= validation_days:
        raise ValueError("Historical data length must be greater than validation_days.")

    # Chronological holdout split: validation_data is strictly unseen by training
    training_data = cleaned_data[:-validation_days]
    validation_data = cleaned_data[-validation_days:]

    # Generate predictions strictly from training_data
    forecast_points = generate_moving_average_forecast(
        training_data,
        forecast_horizon_days=validation_days,
        window_size=window_size,
    )

    actual_values = [float(pt.quantity) for pt in validation_data]
    predicted_values = [float(pt.forecasted_quantity) for pt in forecast_points]

    return calculate_forecast_metrics(
        actual_values=actual_values,
        predicted_values=predicted_values,
        model_name="Simple Moving Average",
    )


def calculate_expected_demand(
    forecast_points: List[DailyForecastPoint],
) -> float:
    """
    Calculates the cumulative expected future demand by summing forecasted daily quantities.

    Args:
        forecast_points: List of DailyForecastPoint objects (from generate_moving_average_forecast).

    Returns:
        Total expected demand rounded to 4 decimal places.

    Raises:
        ValueError: If forecast_points is empty or contains negative forecasted quantities.
    """
    if not forecast_points:
        raise ValueError("Forecast points list cannot be empty.")

    total = 0.0
    for pt in forecast_points:
        if pt.forecasted_quantity < 0.0:
            raise ValueError("Forecasted quantities cannot be negative.")
        total += float(pt.forecasted_quantity)

    return round(total, 4)


def calculate_stockout_risk(
    current_available_stock: int,
    expected_demand_over_lead_time: float,
) -> StockoutRiskMetrics:
    """
    Calculates deterministic stock-out risk level by comparing available stock against
    expected demand over supplier lead time.

    Rules:
    - If D == 0: LOW
    - If D > 0 and S < D: HIGH
    - If D > 0 and D <= S <= 1.5 * D: MEDIUM (S == D is MEDIUM)
    - If D > 0 and S > 1.5 * D: LOW

    Args:
        current_available_stock: Current available stock on hand (must be integer >= 0).
        expected_demand_over_lead_time: Cumulative expected demand over lead time (must be >= 0).

    Returns:
        StockoutRiskMetrics instance.

    Raises:
        ValueError: If current_available_stock < 0 or expected_demand_over_lead_time < 0 or not an int.
    """
    if isinstance(current_available_stock, float):
        if not current_available_stock.is_integer():
            raise ValueError("Current available stock must be an integer.")
        current_available_stock = int(current_available_stock)

    if not isinstance(current_available_stock, int) or isinstance(current_available_stock, bool):
        raise ValueError("Current available stock must be an integer.")

    if current_available_stock < 0:
        raise ValueError("Current available stock cannot be negative.")
    if expected_demand_over_lead_time < 0:
        raise ValueError("Expected demand over lead time cannot be negative.")

    s = float(current_available_stock)
    d = float(expected_demand_over_lead_time)

    if d == 0.0:
        risk_level = "LOW"
    elif s < d:
        risk_level = "HIGH"
    elif d <= s <= 1.5 * d:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return StockoutRiskMetrics(
        current_available_stock=current_available_stock,
        expected_demand_over_lead_time=round(d, 4),
        risk_level=risk_level,
    )
