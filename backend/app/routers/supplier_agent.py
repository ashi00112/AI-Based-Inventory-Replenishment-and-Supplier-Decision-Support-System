"""
Supplier Agent API Router (Member 3).
Provides authenticated endpoint for supplier procurement assessment.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.supplier_agent import SupplierAgentRequest, SupplierAgentResponse
from app.agents.supplier_procurement_agent import SupplierProcurementAgent

router = APIRouter(prefix="/supplier-agent", tags=["Supplier Agent"])


@router.post(
    "/assess",
    response_model=SupplierAgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assess supplier commercial candidates and procurement options (Member 3)",
)
def assess_suppliers(
    request: SupplierAgentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SupplierAgentResponse:
    """
    Evaluates available suppliers for a requested product against commercial terms,
    minimum order quantities, lead times, and grounded procurement/SLA policies.
    Returns structured candidate assessments and an advisory supplier recommendation.
    """
    agent = SupplierProcurementAgent()
    return agent.assess_suppliers(request=request, db=db)
