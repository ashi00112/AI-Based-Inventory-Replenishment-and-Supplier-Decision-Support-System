"""
Replenishment Decision & Supplier Recommendation API Router (Member 4).
Provides endpoints for:
- End-to-end multi-agent replenishment recommendation generation
- Human-in-the-loop decision approval / rejection workflow
- Decision history audit trail and details retrieval
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.agents.decision.agent import DecisionAgent
from app.core.security import InvalidTokenError, decode_access_token
from app.database.session import get_db
from app.dependencies.auth import get_optional_user, require_admin, require_staff_or_admin
from app.models.decision import ApprovalStatus, DecisionRecommendation
from app.models.user import User
from app.schemas.decision import (
    DecisionApprovalRequest,
    DecisionListResponse,
    DecisionRecommendationRequest,
    DecisionRecommendationResponse,
    DemandSnapshot,
    DetectedProcurementCondition,
    InventorySnapshot,
    SelectedSupplierInfo,
    SupplierCandidateOption,
)
from app.services.decision_service import (
    DecisionNotFoundError,
    InvalidApprovalTransitionError,
    approve_decision,
    get_decision,
    list_decisions,
    reject_decision,
    save_decision_recommendation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision", tags=["Decision Agent"])


def _map_model_to_response(model: DecisionRecommendation) -> DecisionRecommendationResponse:
    """Helper to convert a DecisionRecommendation ORM model into a response schema."""
    selected_sup = None
    if model.selected_supplier_id and model.replenishment_required:
        unit_cost = float(model.unit_cost) if model.unit_cost is not None else 0.0
        est_total = float(model.estimated_total_cost) if model.estimated_total_cost is not None else 0.0
        selected_sup = SelectedSupplierInfo(
            supplier_id=model.selected_supplier_id,
            supplier_code=model.selected_supplier.supplier_code if model.selected_supplier else None,
            supplier_name=model.selected_supplier_name or (model.selected_supplier.name if model.selected_supplier else f"Supplier {model.selected_supplier_id}"),
            unit_cost=unit_cost,
            moq=1,
            lead_time_days=model.lead_time_days,
            estimated_total_cost=est_total,
            selection_reason=f"Approved supplier selection for order of {model.recommended_order_quantity} units.",
        )

    # Reconstruct contexts from source payload if available
    inv_context = None
    dem_context = None
    sup_options: List[SupplierCandidateOption] = []

    payload = model.source_agent_payload or {}
    if "inventory_context" in payload:
        try:
            inv_context = InventorySnapshot(**payload["inventory_context"])
        except Exception:
            pass
    if "demand_context" in payload:
        try:
            dem_context = DemandSnapshot(**payload["demand_context"])
        except Exception:
            pass
    if "supplier_options" in payload and isinstance(payload["supplier_options"], list):
        for s in payload["supplier_options"]:
            try:
                sup_options.append(SupplierCandidateOption(**s))
            except Exception:
                pass

    if selected_sup:
        matching = next((s for s in sup_options if s.supplier_id == selected_sup.supplier_id), None)
        if matching:
            if matching.evidence and not selected_sup.evidence:
                selected_sup.evidence = matching.evidence
            if matching.advantages and not selected_sup.advantages:
                selected_sup.advantages = matching.advantages
            if matching.risks and not selected_sup.risks:
                selected_sup.risks = matching.risks

    detected_condition = None
    if "detected_condition" in payload and payload["detected_condition"]:
        try:
            detected_condition = DetectedProcurementCondition(**payload["detected_condition"])
        except Exception:
            pass

    return DecisionRecommendationResponse(
        id=model.id,
        product_id=model.product_id,
        sku=model.product.sku if model.product else None,
        product_name=model.product.name if model.product else f"Product #{model.product_id}",
        replenishment_required=model.replenishment_required,
        recommended_order_quantity=model.recommended_order_quantity,
        selected_supplier=selected_sup,
        risk_level=model.risk_level,
        derived_urgency=payload.get("derived_urgency"),
        effective_urgency=payload.get("effective_urgency"),
        manual_urgency_override=payload.get("manual_urgency_override"),
        manual_override_applied=payload.get("manual_override_applied", False),
        required_delivery_window_days=payload.get("required_delivery_window_days"),
        detected_condition=detected_condition,
        reasoning=model.reasoning,
        factors=model.factors or [],
        warnings=model.warnings or [],
        policy_references=model.policy_references or [],
        confidence=model.confidence,
        approval_status=ApprovalStatus(model.approval_status),
        reviewed_by=model.reviewed_by,
        reviewed_at=model.reviewed_at,
        reviewer_notes=model.reviewer_notes,
        rejection_reason=model.rejection_reason,
        created_at=model.created_at,
        inventory_context=inv_context,
        demand_context=dem_context,
        supplier_options=sup_options,
    )


@router.post(
    "/recommend",
    response_model=DecisionRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Replenishment & Supplier Decision Recommendation (Member 4)",
)
def generate_recommendation(
    request: DecisionRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> DecisionRecommendationResponse:
    """
    Orchestrates the entire multi-agent replenishment pipeline:
    1. Gathers stock intelligence from Inventory Monitoring Agent (Member 1).
    2. Gathers forecast & stockout risk from Demand & Risk Agent (Member 2).
    3. Evaluates suppliers and policies from Supplier Intelligence Agent (Member 3).
    4. Calculates deterministic shortage and selects optimal compliant supplier.
    5. Synthesizes explainable reasoning via Grok LLM with Responsible AI safeguards.
    6. Persists recommendation in PENDING status for human manager review.
    """
    agent = DecisionAgent()
    try:
        response = agent.generate_recommendation(db=db, request=request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "does not exist" in str(exc) else status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Failed to generate replenishment recommendation: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate replenishment decision recommendation.",
        )

    # Persist decision snapshot in PENDING state
    unit_cost = response.selected_supplier.unit_cost if response.selected_supplier else None
    est_total = response.selected_supplier.estimated_total_cost if response.selected_supplier else None
    selected_sup_id = response.selected_supplier.supplier_id if response.selected_supplier else None
    selected_sup_name = response.selected_supplier.supplier_name if response.selected_supplier else None

    source_payload = {
        "inventory_context": response.inventory_context.model_dump(mode="json") if response.inventory_context else None,
        "demand_context": response.demand_context.model_dump(mode="json") if response.demand_context else None,
        "supplier_options": [s.model_dump(mode="json") for s in response.supplier_options],
        "derived_urgency": response.derived_urgency,
        "effective_urgency": response.effective_urgency,
        "manual_urgency_override": response.manual_urgency_override,
        "manual_override_applied": response.manual_override_applied,
        "required_delivery_window_days": response.required_delivery_window_days,
        "detected_condition": response.detected_condition.model_dump(mode="json") if response.detected_condition else None,
    }

    inv_available = response.inventory_context.available_stock if response.inventory_context else 0
    inv_rop = response.inventory_context.reorder_point if response.inventory_context else 0
    dem_total = response.demand_context.total_forecasted_demand if response.demand_context else 0.0
    dem_lt = response.demand_context.expected_demand_over_lead_time if response.demand_context else 0.0
    dem_risk = response.demand_context.risk_level if response.demand_context else "LOW"
    lt_days = response.demand_context.lead_time_days if response.demand_context else 0

    saved_rec = save_decision_recommendation(
        db=db,
        product_id=response.product_id,
        replenishment_required=response.replenishment_required,
        recommended_order_quantity=response.recommended_order_quantity,
        selected_supplier_id=selected_sup_id,
        selected_supplier_name=selected_sup_name,
        unit_cost=unit_cost,
        estimated_total_cost=est_total,
        risk_level=response.risk_level,
        reasoning=response.reasoning,
        factors=response.factors,
        warnings=response.warnings,
        policy_references=response.policy_references,
        confidence=response.confidence,
        forecast_horizon_days=request.forecast_horizon_days,
        lead_time_days=lt_days,
        current_available_stock=inv_available,
        reorder_point=inv_rop,
        predicted_demand=dem_total,
        lead_time_demand=dem_lt,
        stockout_risk_level=dem_risk,
        source_agent_payload=source_payload,
    )

    response.id = saved_rec.id
    response.created_at = saved_rec.created_at
    response.approval_status = ApprovalStatus.PENDING
    return response


@router.get(
    "/history",
    response_model=DecisionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List historical decision recommendations",
)
def get_decision_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    product_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> DecisionListResponse:
    """Returns paginated decision recommendations with optional approval status or product filtering."""
    items, total = list_decisions(
        db=db,
        skip=skip,
        limit=limit,
        status=status_filter,
        product_id=product_id,
    )
    mapped_items = [_map_model_to_response(item) for item in items]
    return DecisionListResponse(items=mapped_items, total=total)


@router.get(
    "/{decision_id}",
    response_model=DecisionRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single decision recommendation details",
)
def get_decision_by_id(
    decision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> DecisionRecommendationResponse:
    """Retrieves full decision recommendation snapshot and audit history."""
    try:
        model = get_decision(db, decision_id)
        return _map_model_to_response(model)
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{decision_id}/approve",
    response_model=DecisionRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Human approval for pending recommendation",
)
def approve_recommendation(
    decision_id: int,
    payload: Optional[DecisionApprovalRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DecisionRecommendationResponse:
    """
    Applies human managerial approval to a pending recommendation.
    Records reviewer ID, notes, and approval timestamp.
    Only ADMIN role is authorized to approve recommendations.
    """
    user_id = current_user.id
    notes = payload.reviewer_notes if payload and payload.reviewer_notes else "Approved by human procurement administrator."

    try:
        updated = approve_decision(db=db, decision_id=decision_id, user_id=user_id, notes=notes)
        return _map_model_to_response(updated)
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidApprovalTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/{decision_id}/reject",
    response_model=DecisionRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Human rejection for pending recommendation",
)
def reject_recommendation(
    decision_id: int,
    payload: Optional[DecisionApprovalRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DecisionRecommendationResponse:
    """
    Records human managerial rejection for a recommendation with justification.
    Only ADMIN role is authorized to reject recommendations.
    """
    user_id = current_user.id
    reason = payload.rejection_reason if payload and payload.rejection_reason else "Rejected by human procurement administrator."

    try:
        updated = reject_decision(db=db, decision_id=decision_id, user_id=user_id, reason=reason)
        return _map_model_to_response(updated)
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidApprovalTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
