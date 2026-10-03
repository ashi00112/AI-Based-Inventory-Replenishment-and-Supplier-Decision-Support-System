from typing import Any, Dict, List, Union

from app.agents.base import BaseAgent
from app.schemas.demand import DemandAgentOutput, DemandDataPoint
from app.services.demand_forecasting import (
    calculate_expected_demand,
    calculate_stockout_risk,
    generate_moving_average_forecast,
    generate_weekday_seasonal_forecast,
    preprocess_demand_data,
    select_best_forecast_model,
)


class DemandRiskAgent(BaseAgent):
    """
    Orchestrator agent for demand forecasting, statistical evaluation, and stock-out risk assessment.
    Conforms to the BaseAgent interface and executes Member 2 deterministic services.
    """
    WINDOW_SIZE: int = 7
    VALIDATION_DAYS: int = 14
    SEASONAL_LOOKBACK_WEEKS: int = 8

    def __init__(self):
        super().__init__("DemandRiskAgent")

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute deterministic demand forecasting, backtesting evaluation, and stock-out risk assessment.

        Args:
            context: Dictionary containing:
                - product_id (int > 0)
                - historical_data (list of dicts or DemandDataPoint objects)
                - forecast_horizon_days (int > 0)
                - lead_time_days (int > 0)
                - current_available_stock (int >= 0)

        Returns:
            Dictionary matching DemandAgentOutput schema structure.

        Raises:
            ValueError: If input context parameters are missing, invalid, or fail contract rules.
        """
        if not isinstance(context, dict):
            raise ValueError("Agent context must be a dictionary.")

        # 1. Validate required product_id
        if "product_id" not in context or context["product_id"] is None:
            raise ValueError("Missing required context parameter: product_id")
        product_id = context["product_id"]
        if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0:
            raise ValueError("product_id must be a positive integer greater than 0.")

        # 2. Validate required forecast_horizon_days
        if "forecast_horizon_days" not in context or context["forecast_horizon_days"] is None:
            raise ValueError("Missing required context parameter: forecast_horizon_days")
        forecast_horizon_days = context["forecast_horizon_days"]
        if not isinstance(forecast_horizon_days, int) or isinstance(forecast_horizon_days, bool) or forecast_horizon_days <= 0:
            raise ValueError("forecast_horizon_days must be a positive integer greater than 0.")

        # 3. Validate required lead_time_days
        if "lead_time_days" not in context or context["lead_time_days"] is None:
            raise ValueError("Missing required context parameter: lead_time_days")
        lead_time_days = context["lead_time_days"]
        if not isinstance(lead_time_days, int) or isinstance(lead_time_days, bool) or lead_time_days <= 0:
            raise ValueError("lead_time_days must be a positive integer greater than 0.")

        # Validate lead time vs horizon constraint
        if lead_time_days > forecast_horizon_days:
            raise ValueError("lead_time_days cannot exceed forecast_horizon_days.")

        # 4. Validate required current_available_stock
        if "current_available_stock" not in context or context["current_available_stock"] is None:
            raise ValueError("Missing required context parameter: current_available_stock")
        current_available_stock = context["current_available_stock"]
        
        if isinstance(current_available_stock, float):
            raise ValueError("current_available_stock must be an integer, not a float.")
        if not isinstance(current_available_stock, int) or isinstance(current_available_stock, bool):
            raise ValueError("current_available_stock must be a non-negative integer.")
        if current_available_stock < 0:
            raise ValueError("current_available_stock cannot be negative.")

        # 5. Validate required historical_data
        if "historical_data" not in context or context["historical_data"] is None:
            raise ValueError("Missing required context parameter: historical_data")
        raw_historical = context["historical_data"]
        if not isinstance(raw_historical, list) or not raw_historical:
            raise ValueError("historical_data must be a non-empty list.")

        # Parse / normalize raw_historical into List[DemandDataPoint] without mutating input
        normalized_history: List[DemandDataPoint] = []
        for entry in raw_historical:
            if isinstance(entry, DemandDataPoint):
                normalized_history.append(entry)
            elif isinstance(entry, dict):
                normalized_history.append(DemandDataPoint(**entry))
            else:
                raise ValueError("Each item in historical_data must be a DemandDataPoint or dict.")

        # 6. Preprocess raw historical demand
        cleaned_data = preprocess_demand_data(normalized_history)

        # 7. Check historical length against VALIDATION_DAYS requirement
        if len(cleaned_data) <= self.VALIDATION_DAYS:
            raise ValueError(
                f"Historical data length ({len(cleaned_data)}) must be greater than "
                f"validation_days ({self.VALIDATION_DAYS}) for model evaluation."
            )

        # 8. Evaluate both SMA and Weekday Seasonal models on holdout and select best model by MAE
        evaluation_metrics = select_best_forecast_model(
            cleaned_data,
            validation_days=self.VALIDATION_DAYS,
            window_size=self.WINDOW_SIZE,
            seasonal_lookback_weeks=self.SEASONAL_LOOKBACK_WEEKS,
        )

        # 9. Generate multi-day future forecasts using selected model on FULL cleaned history
        if evaluation_metrics.selected_model == "Weekday Seasonal Moving Average":
            daily_forecasts = generate_weekday_seasonal_forecast(
                cleaned_data,
                forecast_horizon_days=forecast_horizon_days,
                seasonal_lookback_weeks=self.SEASONAL_LOOKBACK_WEEKS,
            )
        else:
            daily_forecasts = generate_moving_average_forecast(
                cleaned_data,
                forecast_horizon_days=forecast_horizon_days,
                window_size=self.WINDOW_SIZE,
            )

        # 10. Calculate total forecasted demand across full horizon
        total_forecasted_demand = calculate_expected_demand(daily_forecasts)

        # 11. Calculate expected demand during supplier lead time
        lead_time_forecasts = daily_forecasts[:lead_time_days]
        expected_demand_over_lead_time = calculate_expected_demand(lead_time_forecasts)

        # 12. Calculate stock-out risk metrics
        stockout_risk = calculate_stockout_risk(
            current_available_stock=current_available_stock,
            expected_demand_over_lead_time=expected_demand_over_lead_time,
        )

        # 13. Construct output Pydantic model
        output = DemandAgentOutput(
            product_id=product_id,
            forecast_horizon_days=forecast_horizon_days,
            total_forecasted_demand=total_forecasted_demand,
            evaluation_metrics=evaluation_metrics,
            stockout_risk=stockout_risk,
            daily_forecasts=daily_forecasts,
        )

        return output.model_dump()
