from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class DemandDataPoint(BaseModel):
    """
    Standard domain data point representing historical demand for a single date.
    Decoupled from DB persistence models.
    """
    date: date = Field(..., description="Date of historical demand observation")
    quantity: float = Field(..., ge=0.0, description="Observed historical demand quantity (>= 0)")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "date": "2026-09-01",
                "quantity": 25.0,
            }
        },
    )


class DailyDemandPoint(BaseModel):
    """
    Preprocessed continuous daily demand point for a single calendar date.
    """
    date: date = Field(..., description="Calendar date of daily demand")
    quantity: float = Field(..., ge=0.0, description="Aggregated daily demand quantity (>= 0)")

    model_config = ConfigDict(
        extra="forbid",
    )


class DemandAnalysis(BaseModel):
    """
    Descriptive historical demand summary statistics.
    """
    total_demand: float = Field(..., ge=0.0, description="Total aggregated demand across the period (>= 0)")
    average_daily_demand: float = Field(..., ge=0.0, description="Mean daily demand quantity (>= 0)")
    minimum_daily_demand: float = Field(..., ge=0.0, description="Minimum single-day demand quantity (>= 0)")
    maximum_daily_demand: float = Field(..., ge=0.0, description="Maximum single-day demand quantity (>= 0)")
    demand_std_dev: float = Field(..., ge=0.0, description="Standard deviation of daily demand quantities (>= 0)")
    number_of_days: int = Field(..., ge=0, description="Total number of calendar days in the series (>= 0)")

    model_config = ConfigDict(
        extra="forbid",
    )


class ForecastingInput(BaseModel):
    """
    Input schema for triggering a statistical demand forecast execution.
    """
    product_id: int = Field(..., gt=0, description="Product ID to forecast demand for (must be > 0)")
    historical_data: List[DemandDataPoint] = Field(
        ...,
        min_length=1,
        description="Historical demand observations ordered chronologically",
    )
    forecast_horizon_days: int = Field(
        ...,
        gt=0,
        description="Number of future days to forecast (must be > 0)",
    )
    lead_time_days: int = Field(
        ...,
        gt=0,
        description="Supplier lead time in days for risk assessment (must be > 0)",
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class DemandAnalysisRequest(BaseModel):
    """
    HTTP Request payload schema for triggering demand analysis and stock-out risk assessment.
    """
    product_id: int = Field(..., gt=0, description="Product ID to analyze (must be > 0)")
    historical_data: List[DemandDataPoint] = Field(
        ...,
        min_length=1,
        description="Historical daily demand observations ordered chronologically",
    )
    forecast_horizon_days: int = Field(
        ...,
        gt=0,
        description="Number of future days to forecast (must be > 0)",
    )
    lead_time_days: int = Field(
        ...,
        gt=0,
        description="Supplier delivery lead time in days (must be > 0)",
    )
    current_available_stock: StrictInt = Field(
        ...,
        ge=0,
        description="Current available stock on hand as integer whole units (must be >= 0)",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "product_id": 1,
                "historical_data": [
                    {"date": "2026-09-01", "quantity": 10.0},
                    {"date": "2026-09-02", "quantity": 20.0},
                    {"date": "2026-09-03", "quantity": 15.0},
                ],
                "forecast_horizon_days": 10,
                "lead_time_days": 3,
                "current_available_stock": 50,
            }
        },
    )


class EvaluationMetrics(BaseModel):
    """
    Statistical accuracy metrics for backtesting and model evaluation.
    """
    mae: float = Field(..., ge=0.0, description="Mean Absolute Error (>= 0)")
    rmse: float = Field(..., ge=0.0, description="Root Mean Squared Error (>= 0)")
    mape: float = Field(..., ge=0.0, description="Mean Absolute Percentage Error (>= 0)")
    selected_model: str = Field(
        ...,
        min_length=1,
        description="Identifier/name of the selected statistical model",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class DailyForecastPoint(BaseModel):
    """
    Forecasted demand value for a specific future date.
    """
    date: date = Field(..., description="Future forecast date")
    forecasted_quantity: float = Field(
        ...,
        ge=0.0,
        description="Forecasted demand quantity (must be >= 0)",
    )
    confidence_interval_lower: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Lower bound of forecast confidence interval (>= 0)",
    )
    confidence_interval_upper: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Upper bound of forecast confidence interval (>= 0)",
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="after")
    def validate_confidence_interval(self) -> "DailyForecastPoint":
        if (
            self.confidence_interval_lower is not None
            and self.confidence_interval_upper is not None
        ):
            if self.confidence_interval_lower > self.confidence_interval_upper:
                raise ValueError("Lower confidence bound cannot exceed upper confidence bound.")
        return self


class StockoutRiskMetrics(BaseModel):
    """
    Simplified stock-out risk summary metrics.
    """
    current_available_stock: int = Field(
        ...,
        ge=0,
        description="Current available stock on hand (>= 0)",
    )
    expected_demand_over_lead_time: float = Field(
        ...,
        ge=0.0,
        description="Expected cumulative demand over supplier lead time (>= 0)",
    )
    risk_level: str = Field(
        ...,
        min_length=1,
        description="Categorical risk assessment level (e.g. LOW, MEDIUM, HIGH, CRITICAL)",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class DemandAgentOutput(BaseModel):
    """
    Structured numerical output payload for Member 4 Replenishment Decision Agent.
    Strictly contains deterministic numerical calculations and metrics.
    """
    product_id: int = Field(..., gt=0, description="Product ID (must be > 0)")
    forecast_horizon_days: int = Field(..., gt=0, description="Forecast horizon in days (must be > 0)")
    total_forecasted_demand: float = Field(
        ...,
        ge=0.0,
        description="Sum of forecasted quantities over horizon (>= 0)",
    )
    evaluation_metrics: EvaluationMetrics = Field(
        ...,
        description="Evaluation error metrics for selected model",
    )
    stockout_risk: StockoutRiskMetrics = Field(
        ...,
        description="Stock-out risk metrics over lead time",
    )
    daily_forecasts: List[DailyForecastPoint] = Field(
        ...,
        description="List of daily forecasted data points",
    )

    model_config = ConfigDict(
        extra="forbid",
    )
