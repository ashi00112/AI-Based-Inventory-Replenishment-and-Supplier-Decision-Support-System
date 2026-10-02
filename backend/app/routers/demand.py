from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.demand import DemandRiskAgent
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.demand import DemandAgentOutput, DemandAnalysisRequest

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
