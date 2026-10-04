from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.agents.demand import DemandRiskAgent
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.demand import (
    DemandAgentOutput,
    DemandAnalysisDBRequest,
    DemandAnalysisRequest,
)
from app.services.demand_integration_service import (
    DemandIntegrationError,
    NoSalesHistoryError,
    analyze_product_demand_from_db,
)
from app.services.inventory_service import InventoryNotFoundError
from app.services.product_service import ProductNotFoundError

router = APIRouter()


@router.post(
    "/analyze",
    response_model=DemandAgentOutput,
    status_code=status.HTTP_200_OK,
    summary="Execute demand forecasting and stock-out risk analysis",
    description=(
        "Orchestrates historical demand preprocessing, Simple Moving Average (SMA) forecasting, "
        "backtesting evaluation metrics, and lead-time stock-out risk assessment via DemandRiskAgent."
    ),
)
def analyze_demand(
    payload: DemandAnalysisRequest,
    current_user: User = Depends(get_current_user),
) -> DemandAgentOutput:
    """
    Protected demand analysis endpoint.
    Accepts historical demand, forecast horizon, supplier lead time, and current available stock.
    Returns structured DemandAgentOutput containing evaluation metrics, stock-out risk level, and daily forecasts.
    """
    try:
        agent = DemandRiskAgent()
        result = agent.run(payload.model_dump())
        return DemandAgentOutput(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/analyze/{product_id}",
    response_model=DemandAgentOutput,
    status_code=status.HTTP_200_OK,
    summary="Execute DB-backed demand forecasting and stock-out risk analysis for a product",
    description=(
        "Retrieves historical sales history and current available stock from database models for product_id, "
        "and executes DemandRiskAgent forecasting, model selection, projected stock trajectory, and stock-out risk assessment."
    ),
)
def analyze_product_demand(
    product_id: int = Path(..., gt=0, description="Product ID to analyze (must be > 0)"),
    payload: DemandAnalysisDBRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DemandAgentOutput:
    """
    Protected database-backed demand analysis endpoint.
    Loads sales history and current stock from DB for product_id.
    Returns structured DemandAgentOutput.
    """
    try:
        result = analyze_product_demand_from_db(
            db=db,
            product_id=product_id,
            forecast_horizon_days=payload.forecast_horizon_days,
            lead_time_days=payload.lead_time_days,
        )
        return DemandAgentOutput(**result)
    except (ProductNotFoundError, InventoryNotFoundError, NoSalesHistoryError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except DemandIntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
