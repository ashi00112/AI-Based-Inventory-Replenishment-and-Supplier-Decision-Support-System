"""
Deterministic Decision Engine & Business Logic Service (Member 4).
Handles:
- Deterministic replenishment shortage and safety stock calculation.
- Guaranteed safeguards (recommended_order_quantity >= 0, integer rounding).
- Supplier candidate evaluation, policy constraint verification, and selection.
- Grounded explanation synthesis and fallback rationale.
- Missing data safeguards preventing hallucinations.
- Database persistence and human-in-the-loop approval workflows.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.decision import ApprovalStatus, DecisionRecommendation
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User

logger = logging.getLogger(__name__)


class DecisionServiceError(Exception):
    """Base domain exception for Decision Service errors."""
    pass


class DecisionNotFoundError(DecisionServiceError):
    """Raised when a requested decision recommendation record does not exist."""
    pass


class InvalidApprovalTransitionError(DecisionServiceError):
    """Raised when an approval state transition is illegal (e.g. already finalized)."""
    pass


def calculate_replenishment_shortage(
    available_stock: int,
    reorder_point: int,
    predicted_demand: float,
    safety_stock: Optional[int] = None,
) -> Tuple[bool, int, Dict[str, Any]]:
    """
    Deterministic calculation of replenishment requirement and raw target order quantity.

    Mathematical Formula:
        required_safety_stock = safety_stock if safety_stock is not None else reorder_point
        net_requirement = (predicted_demand + required_safety_stock) - available_stock

    Decision Rules:
        - Replenishment is triggered if:
            1. available_stock <= reorder_point, OR
            2. predicted_demand > available_stock, OR
            3. net_requirement > 0
        - If replenishment is required:
            recommended_quantity = max(0, ceil(net_requirement))
        - If replenishment is NOT required:
            recommended_quantity = 0

    Safeguards:
        - Enforces recommended_quantity >= 0 always.
        - Clamps floats to integers using ceil to prevent stock deficit.
    """
    # Defensive normalization
    safe_available = max(0, int(available_stock))
    safe_reorder_point = max(0, int(reorder_point))
    safe_demand = max(0.0, float(predicted_demand))

    effective_safety_stock = safe_reorder_point if safety_stock is None else max(0, int(safety_stock))

    # Calculate net shortage requirement
    net_requirement = (safe_demand + effective_safety_stock) - safe_available

    is_low_stock = safe_available <= safe_reorder_point
    is_demand_exceeding = safe_demand > safe_available
    has_shortage = net_requirement > 0

    replenishment_required = is_low_stock or is_demand_exceeding or has_shortage

    if replenishment_required:
        # Round up to whole units to fully protect against stockouts
        raw_quantity = max(0, int(math.ceil(net_requirement)))
        # If stock is below reorder point but net_requirement calculates small, order at least the deficit to ROP
        rop_deficit = max(0, safe_reorder_point - safe_available)
        raw_quantity = max(raw_quantity, rop_deficit)
    else:
        raw_quantity = 0

    # Strict invariant safeguard
    raw_quantity = max(0, raw_quantity)

    metrics = {
        "available_stock": safe_available,
        "reorder_point": safe_reorder_point,
        "effective_safety_stock": effective_safety_stock,
        "predicted_demand": safe_demand,
        "net_requirement": round(net_requirement, 2),
        "is_low_stock": is_low_stock,
        "is_demand_exceeding": is_demand_exceeding,
    }

    return replenishment_required, raw_quantity, metrics


def select_best_supplier_candidate(
    candidates: List[Dict[str, Any]],
    recommended_quantity: int,
    urgency: str = "normal",
    policy_constraints: Optional[List[str]] = None,
    advisory_supplier_id: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], int, List[str], List[str]]:
    """
    Selects the optimal supplier candidate strictly adhering to commercial and policy criteria.

    Selection Rules:
        1. Filters only active candidates.
        2. Filters out candidates violating explicit negative policy restrictions.
        3. If replenishment is required:
           - Adjusts quantity to satisfy the supplier's Minimum Order Quantity (MOQ).
             final_quantity = max(recommended_quantity, candidate.moq)
        4. Ranking Criteria:
           - If urgency == "emergency" or "high":
             Prioritizes shortest lead_time_days first, then lowest unit_cost.
           - If urgency == "normal":
             Prioritizes lowest unit_cost first, then shortest lead_time_days.
           - Advisory recommendation from Member 3 breaks ties or acts as preferred candidate
             if compliant with constraints.
    """
    warnings: List[str] = []
    factors: List[str] = []

    if not candidates:
        warnings.append("No active suppliers found in catalog for this product.")
        return None, recommended_quantity, warnings, factors

    valid_candidates: List[Dict[str, Any]] = []

    for c in candidates:
        supplier_id = c.get("supplier_id")
        name = c.get("supplier_name", f"Supplier {supplier_id}")
        unit_cost = float(c.get("unit_cost", 0.0))
        moq = int(c.get("moq", 1))
        lead_time = int(c.get("lead_time_days", 0))

        # Check policy restrictions (e.g. suspended, high defect rate, restricted vendor)
        risks = [r.lower() for r in c.get("risks", [])]
        is_restricted = any("restricted" in r or "suspended" in r or "blacklisted" in r for r in risks)
        if is_restricted:
            warnings.append(f"Supplier '{name}' excluded due to compliance/policy restriction.")
            continue

        valid_candidates.append(c)

    if not valid_candidates:
        warnings.append("All supplier candidates are disqualified by policy or status restrictions.")
        return None, recommended_quantity, warnings, factors

    # Sort candidates based on urgency
    norm_urgency = (urgency or "normal").strip().lower()

    def candidate_sort_key(c: Dict[str, Any]) -> Tuple[Any, ...]:
        lead_time = int(c.get("lead_time_days", 999))
        unit_cost = float(c.get("unit_cost", 1e9))
        is_advisory = 0 if c.get("supplier_id") == advisory_supplier_id else 1

        if norm_urgency in ("emergency", "high"):
            # Lead time is paramount during stockout urgency
            return (lead_time, unit_cost, is_advisory)
        else:
            # Cost efficiency is paramount during normal replenishment
            return (unit_cost, lead_time, is_advisory)

    valid_candidates.sort(key=candidate_sort_key)
    chosen = valid_candidates[0]

    chosen_moq = int(chosen.get("moq", 1))
    final_quantity = recommended_quantity

    # MOQ adjustment safeguard
    if recommended_quantity > 0 and final_quantity < chosen_moq:
        final_quantity = chosen_moq
        factors.append(
            f"Order quantity adjusted up to {chosen_moq} units to satisfy '{chosen['supplier_name']}' MOQ policy."
        )

    # Note trade-offs
    factors.append(
        f"Selected '{chosen['supplier_name']}' based on {norm_urgency} procurement criteria: "
        f"unit cost LKR {chosen['unit_cost']:,.2f}, lead time {chosen['lead_time_days']} days, MOQ {chosen_moq} units."
    )

    if chosen.get("supplier_id") == advisory_supplier_id:
        factors.append("Selection aligns with Supplier Intelligence Agent advisory preference.")

    return chosen, final_quantity, warnings, factors


def generate_deterministic_explanation(
    product_name: str,
    replenishment_required: bool,
    quantity: int,
    selected_supplier: Optional[Dict[str, Any]],
    risk_level: str,
    available_stock: int,
    reorder_point: int,
    predicted_demand: float,
    warnings: List[str],
) -> Tuple[str, List[str]]:
    """
    Generates a deterministic, factual explanation and key factor list.
    Ensures explainability is always available even if Grok is offline or unconfigured.
    """
    factors = [
        f"Current available inventory: {available_stock} units (Reorder Point: {reorder_point} units).",
        f"Forecasted demand over horizon: {predicted_demand:.1f} units.",
        f"Assessed stockout risk level: {risk_level}.",
    ]

    if replenishment_required:
        supplier_info = (
            f"Recommended procurement order of {quantity} units designated to '{selected_supplier['supplier_name']}' "
            f"at LKR {selected_supplier['unit_cost']:,.2f}/unit (Lead time: {selected_supplier['lead_time_days']} days)."
            if selected_supplier
            else f"Recommended procurement order of {quantity} units. (No compliant supplier currently selected)."
        )

        reasoning = (
            f"Replenishment is REQUIRED for '{product_name}'. Net available inventory ({available_stock} units) "
            f"is insufficient to satisfy the forecasted demand of {predicted_demand:.1f} units and maintain safety stock "
            f"(ROP: {reorder_point} units). {supplier_info}"
        )
    else:
        reasoning = (
            f"Replenishment is NOT REQUIRED for '{product_name}'. Net available inventory ({available_stock} units) "
            f"comfortably exceeds the safety reorder point ({reorder_point} units) and satisfies forecasted "
            f"demand ({predicted_demand:.1f} units). No immediate purchase order is necessary."
        )

    return reasoning, factors


# =========================================================================
# DATABASE PERSISTENCE & HUMAN APPROVAL WORKFLOWS
# =========================================================================

def save_decision_recommendation(
    db: Session,
    product_id: int,
    replenishment_required: bool,
    recommended_order_quantity: int,
    selected_supplier_id: Optional[int],
    selected_supplier_name: Optional[str],
    unit_cost: Optional[float],
    estimated_total_cost: Optional[float],
    risk_level: str,
    reasoning: str,
    factors: List[str],
    warnings: List[str],
    policy_references: List[str],
    confidence: Optional[float],
    forecast_horizon_days: int = 14,
    lead_time_days: int = 0,
    current_available_stock: int = 0,
    reorder_point: int = 0,
    predicted_demand: float = 0.0,
    lead_time_demand: float = 0.0,
    stockout_risk_level: str = "LOW",
    source_agent_payload: Optional[Dict[str, Any]] = None,
) -> DecisionRecommendation:
    """
    Persists a synthesized decision recommendation into PostgreSQL/SQLite in PENDING state.
    """
    decision = DecisionRecommendation(
        product_id=product_id,
        forecast_horizon_days=forecast_horizon_days,
        lead_time_days=lead_time_days,
        current_available_stock=current_available_stock,
        reorder_point=reorder_point,
        predicted_demand=predicted_demand,
        lead_time_demand=lead_time_demand,
        stockout_risk_level=stockout_risk_level,
        replenishment_required=replenishment_required,
        recommended_order_quantity=recommended_order_quantity,
        selected_supplier_id=selected_supplier_id,
        selected_supplier_name=selected_supplier_name,
        unit_cost=Decimal(str(round(unit_cost, 2))) if unit_cost is not None else None,
        estimated_total_cost=Decimal(str(round(estimated_total_cost, 2))) if estimated_total_cost is not None else None,
        risk_level=risk_level,
        reasoning=reasoning,
        factors=factors or [],
        warnings=warnings or [],
        policy_references=policy_references or [],
        confidence=confidence,
        approval_status=ApprovalStatus.PENDING.value,
        source_agent_payload=source_agent_payload,
    )

    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def get_decision(db: Session, decision_id: int) -> DecisionRecommendation:
    """Retrieves a specific decision recommendation by primary key."""
    decision = db.get(DecisionRecommendation, decision_id)
    if not decision:
        raise DecisionNotFoundError(f"Decision recommendation with ID {decision_id} not found.")
    return decision


def list_decisions(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    product_id: Optional[int] = None,
) -> Tuple[List[DecisionRecommendation], int]:
    """Retrieves paginated decision recommendations with optional filters."""
    query = select(DecisionRecommendation).order_by(DecisionRecommendation.created_at.desc())

    if status:
        query = query.where(DecisionRecommendation.approval_status == status.upper())
    if product_id:
        query = query.where(DecisionRecommendation.product_id == product_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.offset(skip).limit(limit)).all())
    return items, total


def approve_decision(
    db: Session,
    decision_id: int,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> DecisionRecommendation:
    """
    Transitions a decision recommendation to APPROVED status with human manager audit trail.
    """
    decision = get_decision(db, decision_id)

    if decision.approval_status != ApprovalStatus.PENDING.value:
        raise InvalidApprovalTransitionError(
            f"Cannot approve decision {decision_id}: current status is '{decision.approval_status}'."
        )

    decision.approval_status = ApprovalStatus.APPROVED.value
    decision.reviewed_by = user_id
    decision.reviewed_at = datetime.now(timezone.utc)
    decision.reviewer_notes = notes

    db.commit()
    db.refresh(decision)
    return decision


def reject_decision(
    db: Session,
    decision_id: int,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> DecisionRecommendation:
    """
    Transitions a decision recommendation to REJECTED status with mandatory/optional reason.
    """
    decision = get_decision(db, decision_id)

    if decision.approval_status != ApprovalStatus.PENDING.value:
        raise InvalidApprovalTransitionError(
            f"Cannot reject decision {decision_id}: current status is '{decision.approval_status}'."
        )

    decision.approval_status = ApprovalStatus.REJECTED.value
    decision.reviewed_by = user_id
    decision.reviewed_at = datetime.now(timezone.utc)
    decision.rejection_reason = reason or "No specific rejection reason provided."

    db.commit()
    db.refresh(decision)
    return decision
