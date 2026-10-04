"""
Deterministic Decision Engine & Business Logic Service (Member 4).
Handles:
- Deterministic replenishment shortage and safety stock calculation.
- Guaranteed safeguards (recommended_order_quantity >= 0, integer rounding).
- Automatic delivery window & timing metrics (days_until_unsafe, days_until_stockout).
- Automatic procurement urgency derivation (Normal, High, Emergency) with manual override audit.
- Delivery slack calculation and feasibility gating.
- Grounded extraction of SLA signals (OTIF, expedited support, delay risk).
- Situation-aware candidate scoring across Cost, Delivery, and SLA dimensions.
- Grounded explanation synthesis and fallback rationale.
- Database persistence and human-in-the-loop approval workflows.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.decision import ApprovalStatus, DecisionRecommendation
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.decision import ScoreBreakdown, SupplierPolicySignals

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


# =========================================================================
# 1. DETERMINISTIC REPLENISHMENT SHORTAGE CALCULATION
# =========================================================================

def calculate_replenishment_shortage(
    available_stock: int,
    reorder_point: int,
    predicted_demand: float,
    incoming_stock: int = 0,
    safety_stock: Optional[int] = None,
) -> Tuple[bool, int, Dict[str, Any]]:
    """
    Deterministic calculation of replenishment requirement and raw target order quantity.

    Business Rules:
        - Reorder point is used as SmartSupply's effective safety-stock buffer.
        - Incoming stock is treated as confirmed pipeline inventory expected to arrive
          within the active replenishment planning horizon.
        - Effective inventory position:
            effective_inventory = available_stock + incoming_stock
        - Effective safety-stock buffer:
            effective_safety_stock = reorder_point if safety_stock is None else max(0, int(safety_stock))
        - Net requirement:
            net_requirement = (predicted_demand + effective_safety_stock) - effective_inventory

    Decision Rules:
        - Replenishment is triggered if:
            net_requirement > 0 (or effective_inventory < reorder_point when demand is zero)
        - If replenishment is required:
            raw_quantity = max(0, ceil(net_requirement))
            effective_deficit = max(0, safe_reorder_point - effective_inventory)
            raw_quantity = max(raw_quantity, effective_deficit)
        - If replenishment is NOT required:
            raw_quantity = 0

    Safeguards:
        - Enforces raw_quantity >= 0 always.
        - Clamps floats to integers using ceil to prevent stock deficit.
    """
    safe_available = max(0, int(available_stock))
    safe_incoming_stock = max(0, int(incoming_stock))
    safe_reorder_point = max(0, int(reorder_point))
    safe_demand = max(0.0, float(predicted_demand))

    effective_inventory = safe_available + safe_incoming_stock
    effective_safety_stock = safe_reorder_point if safety_stock is None else max(0, int(safety_stock))

    # Calculate net shortage requirement
    net_requirement = (safe_demand + effective_safety_stock) - effective_inventory

    # Replenishment triggers when projected effective inventory is insufficient to satisfy
    # forecast demand + retained reorder-point buffer (or effective inventory falls below ROP buffer).
    has_shortage = net_requirement > 0
    is_effective_low_stock = effective_inventory < safe_reorder_point
    replenishment_required = has_shortage or is_effective_low_stock

    if replenishment_required:
        raw_quantity = max(0, int(math.ceil(net_requirement)))
        effective_deficit = max(0, safe_reorder_point - effective_inventory)
        raw_quantity = max(raw_quantity, effective_deficit)
    else:
        raw_quantity = 0

    raw_quantity = max(0, raw_quantity)

    metrics = {
        "available_stock": safe_available,
        "incoming_stock": safe_incoming_stock,
        "effective_inventory": effective_inventory,
        "reorder_point": safe_reorder_point,
        "effective_safety_stock": effective_safety_stock,
        "predicted_demand": safe_demand,
        "net_requirement": round(net_requirement, 4),
        "raw_quantity": raw_quantity,
        "is_low_stock": safe_available <= safe_reorder_point,
        "is_effective_low_stock": is_effective_low_stock,
        "is_demand_exceeding": safe_demand > effective_inventory,
        "has_shortage": has_shortage,
    }

    return replenishment_required, raw_quantity, metrics


# =========================================================================
# 2. REQUIRED DELIVERY WINDOW & TIMING METRICS
# =========================================================================

def derive_delivery_window_and_timing(
    available_stock: int,
    reorder_point: int,
    daily_forecasts: List[Any],
    forecast_horizon_days: int = 14,
    incoming_stock: int = 0,
) -> Dict[str, Any]:
    """
    Determines the earliest point where projected inventory becomes unsafe,
    and calculates the required delivery window.

    Rules:
        - SmartSupply treats reorder_point as the effective safety-stock buffer.
        - days_until_unsafe: the first forecast day where projected inventory falls below the ROP buffer.
          Calculated using confirmed pipeline inventory (effective_inventory = available + incoming).
        - days_until_stockout: the first forecast day where physical stock on hand reaches zero (without incoming).
        - required_delivery_window_days:
            If days_until_unsafe is defined and > 0 -> days_until_unsafe.
            If inventory is already below ROP on Day 0 (days_until_unsafe == 0) ->
                if days_until_stockout is defined and > 0 -> days_until_stockout.
                else -> 1 day (immediate emergency).
            If stock never drops below ROP within horizon -> forecast_horizon_days.
    """
    safe_available = max(0, int(available_stock))
    safe_incoming = max(0, int(incoming_stock))
    safe_rop = max(0, int(reorder_point))
    effective_inventory = safe_available + safe_incoming

    days_until_buffer_breach: Optional[int] = None
    days_until_stockout: Optional[int] = None

    # Check Day 0 conditions
    if effective_inventory < safe_rop:
        days_until_buffer_breach = 0
    if safe_available <= 0:
        days_until_stockout = 0

    # Project day-by-day trajectories using daily forecasts
    if daily_forecasts:
        proj_effective = float(effective_inventory)
        proj_physical = float(safe_available)

        for day_idx, pt in enumerate(daily_forecasts, start=1):
            if hasattr(pt, "forecasted_quantity"):
                demand_qty = float(pt.forecasted_quantity)
            elif isinstance(pt, dict):
                demand_qty = float(pt.get("forecasted_quantity", 0.0))
            else:
                demand_qty = 0.0

            # Effective stock trajectory (ROP buffer breach check)
            proj_effective = round(proj_effective - demand_qty, 4)
            if proj_effective < float(safe_rop) and days_until_buffer_breach is None:
                days_until_buffer_breach = day_idx

            # Physical stock trajectory (physical stockout check: stock <= 0)
            proj_physical = round(proj_physical - demand_qty, 4)
            if proj_physical <= 0.0 and days_until_stockout is None:
                days_until_stockout = day_idx

    days_until_unsafe = days_until_buffer_breach  # backward-compatible alias

    # Determine required delivery window using earliest meaningful critical deadline:
    if days_until_stockout is not None and days_until_stockout == 0:
        # Immediate physical stockout on Day 0
        required_window = 1
    elif days_until_stockout is not None and days_until_stockout > 0 and (
        days_until_buffer_breach is None
        or days_until_buffer_breach == 0
        or days_until_stockout <= days_until_buffer_breach
    ):
        # Physical stockout is projected and occurs before/at buffer breach, or buffer was already breached on Day 0
        required_window = max(1, days_until_stockout)
    elif days_until_buffer_breach is not None and days_until_buffer_breach > 0:
        # Buffer breach is projected before physical stockout
        required_window = max(1, days_until_buffer_breach)
    elif days_until_buffer_breach is not None and days_until_buffer_breach == 0:
        # Buffer already breached on Day 0 and no future stockout projected
        required_window = 1
    elif days_until_stockout is not None and days_until_stockout > 0:
        required_window = max(1, days_until_stockout)
    else:
        # Stock remains safe throughout forecast horizon
        required_window = max(1, int(forecast_horizon_days))

    return {
        "days_until_buffer_breach": days_until_buffer_breach,
        "days_until_unsafe": days_until_unsafe,
        "days_until_stockout": days_until_stockout,
        "required_delivery_window_days": required_window,
        "effective_inventory": effective_inventory,
        "available_stock": safe_available,
        "incoming_stock": safe_incoming,
        "reorder_point": safe_rop,
    }


# =========================================================================
# 3. AUTOMATIC PROCUREMENT URGENCY DERIVATION
# =========================================================================

def derive_procurement_urgency(
    replenishment_required: bool,
    stockout_risk_level: str,
    days_until_unsafe: Optional[int],
    days_until_stockout: Optional[int],
    required_delivery_window_days: int,
    active_lead_times: List[int],
    available_stock: int,
    reorder_point: int,
    days_until_buffer_breach: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Deterministic function deriving procurement urgency based on actual available system information.

    Concept:
        - NO REPLENISHMENT -> normal display state.
        - EMERGENCY:
            Very little delivery time remains (window <= min active lead time, or physical stockout <= 2 days, or stock=0).
            Delivery continuity dominates cost.
        - HIGH:
            Stock is becoming unsafe soon (window < max active lead time, or stockout risk HIGH, or days_until_buffer_breach <= 5).
            Delivery suitability and cost BOTH matter.
        - NORMAL:
            Sufficient delivery time exists; eligible suppliers can satisfy delivery window comfortably.
            Cost efficiency dominates.

    Returns:
        (urgency: 'normal' | 'high' | 'emergency', reason: str)
    """
    if not replenishment_required:
        return "normal", "No replenishment is currently required; normal inventory buffer maintained."

    min_lead = min(active_lead_times) if active_lead_times else 3
    max_lead = max(active_lead_times) if active_lead_times else 7
    norm_risk = (stockout_risk_level or "LOW").strip().upper()
    breach_days = days_until_buffer_breach if days_until_buffer_breach is not None else days_until_unsafe

    # EMERGENCY triggers:
    # 1. Physical stock is completely exhausted (available <= 0)
    # 2. Physical stockout is projected within 2 days
    # 3. Required delivery window is at or below the fastest supplier's lead time
    if (
        available_stock <= 0
        or (days_until_stockout is not None and days_until_stockout <= 2)
        or (required_delivery_window_days <= min_lead and breach_days is not None and breach_days <= 2)
    ):
        if days_until_stockout is not None and breach_days is not None and days_until_stockout < breach_days:
            reason = (
                f"Although the reorder-point buffer is projected to be breached in {breach_days} days, "
                f"available-to-fulfil inventory may be exhausted in approximately {days_until_stockout} days. "
                f"The {days_until_stockout}-day stockout horizon therefore governs supplier delivery feasibility."
            )
        elif days_until_stockout is not None:
            reason = (
                f"Available-to-fulfil inventory exhaustion is projected in approximately {days_until_stockout} days (delivery window: {required_delivery_window_days} days). "
                f"Delivery continuity dominates cost, requiring the fastest compliant expedited fulfillment."
            )
        elif available_stock <= 0:
            reason = (
                f"Available-to-fulfil inventory is completely exhausted (0 available units). "
                f"Immediate emergency replenishment required."
            )
        else:
            reason = (
                f"Required delivery window ({required_delivery_window_days} days) does not exceed minimum supplier lead time ({min_lead} days). "
                f"Delivery continuity dominates cost under EMERGENCY protocol."
            )
        return "emergency", reason

    # HIGH triggers:
    # 1. Required delivery window cannot be met by all active suppliers (window < max_lead)
    # 2. Demand Agent risk level is HIGH
    # 3. Inventory falls below ROP buffer within 5 days
    if (
        required_delivery_window_days < max_lead
        or norm_risk == "HIGH"
        or (breach_days is not None and breach_days <= 5)
    ):
        if days_until_stockout is not None and breach_days is not None and days_until_stockout < breach_days:
            reason = (
                f"Although the reorder-point buffer is projected to be breached in {breach_days} days, "
                f"available-to-fulfil inventory may be exhausted in approximately {days_until_stockout} days. "
                f"The {days_until_stockout}-day stockout horizon therefore governs supplier delivery feasibility."
            )
        else:
            reason = (
                f"Projected inventory is expected to become unsafe within approximately "
                f"{required_delivery_window_days} days, so supplier delivery capability must be prioritized alongside cost."
            )
        return "high", reason

    # NORMAL:
    reason = (
        f"Sufficient delivery time exists ({required_delivery_window_days} days >= max supplier lead time {max_lead} days). "
        f"Eligible suppliers can satisfy the delivery window comfortably, so cost efficiency is prioritized."
    )
    return "normal", reason


# =========================================================================
# 4. GROUNDED SLA DECISION SIGNALS EXTRACTION
# =========================================================================

def extract_supplier_policy_signals(
    candidate: Dict[str, Any],
    evidence_list: Optional[List[Any]] = None,
) -> SupplierPolicySignals:
    """
    Extracts structured, grounded SLA decision signals from retrieved document evidence.
    Every signal MUST be backed by retrieved text. If no evidence exists, fields default to unknown/neutral.
    """
    ev_items = evidence_list or candidate.get("evidence") or []
    collected_text = ""
    evidence_refs: List[int] = []

    for ev in ev_items:
        if isinstance(ev, dict):
            text = ev.get("text", "")
            doc_id = ev.get("document_id")
        else:
            text = getattr(ev, "text", "")
            doc_id = getattr(ev, "document_id", None)
        collected_text += " " + text.lower()
        if doc_id and doc_id not in evidence_refs:
            evidence_refs.append(int(doc_id))

    for r in (candidate.get("risks") or []):
        collected_text += " " + str(r).lower()

    compliance_status = "eligible"
    expedited_support = "unknown"
    emergency_suitability = "unknown"
    high_risk_suitability = "unknown"
    bulk_suitability = "unknown"
    delay_risk = "unknown"
    otif_target: Optional[float] = None
    reliability_score: Optional[float] = None

    if collected_text:
        # Compliance check
        if any(term in collected_text for term in ["restricted", "suspended", "blacklisted", "disqualified"]):
            compliance_status = "restricted"

        # Expedited support & Emergency suitability
        if any(term in collected_text for term in ["emergency dispatch", "expedited orders", "emergency orders", "rapid-fulfillment", "emergency procurement", "emergency replenishment"]):
            if any(term in collected_text for term in ["not guaranteed", "not supported", "cannot be expedited", "not suitable"]):
                expedited_support = "limited"
                emergency_suitability = "limited"
            elif any(term in collected_text for term in ["outstanding choice for emergency", "rapid delivery compliance", "preferred"]):
                expedited_support = "strong"
                emergency_suitability = "preferred"
            else:
                expedited_support = "strong"
                emergency_suitability = "preferred"
        elif "expedited" in collected_text or "emergency" in collected_text:
            if any(term in collected_text for term in ["not guaranteed", "not supported", "cannot be expedited", "not suitable"]):
                expedited_support = "limited"
                emergency_suitability = "limited"
            else:
                expedited_support = "supported"
                emergency_suitability = "acceptable"

        # High risk suitability
        if "priority dispatch" in collected_text or "high-risk priority" in collected_text:
            high_risk_suitability = "preferred"
        elif "balanced-tier" in collected_text or "balanced" in collected_text:
            high_risk_suitability = "acceptable"
        elif "cannot be expedited" in collected_text or "not suitable" in collected_text or "cannot be expedited through standard freight" in collected_text:
            high_risk_suitability = "limited"

        # Bulk suitability
        if "bulk replenishment" in collected_text or "wholesale" in collected_text or "bulk qualified" in collected_text:
            bulk_suitability = "preferred"

        # Delay risk
        if "variance +/- 2" in collected_text or "elevated variance" in collected_text or "delivery variance" in collected_text:
            delay_risk = "high"
        elif "99.1% rapid" in collected_text or "benchmark standard" in collected_text or "low defect rate" in collected_text or "reliable" in collected_text or "good standing" in collected_text:
            delay_risk = "low"

        # OTIF extraction
        otif_match = re.search(r"otif.*?(\d{2}(?:\.\d+)?)%", collected_text)
        if not otif_match:
            otif_match = re.search(r"(\d{2}(?:\.\d+)?)%.*?otif", collected_text)
        if otif_match:
            try:
                otif_target = float(otif_match.group(1))
            except ValueError:
                pass

        # Reliability score extraction
        rel_match = re.search(r"overall score.*?(\d{2}(?:\.\d+)?)", collected_text)
        if not rel_match:
            rel_match = re.search(r"reliability (?:score|rate).*?(\d{2}(?:\.\d+)?)", collected_text)
        if rel_match:
            try:
                reliability_score = float(rel_match.group(1))
            except ValueError:
                pass

    return SupplierPolicySignals(
        compliance_status=compliance_status,
        expedited_support=expedited_support,
        reliability_score=reliability_score,
        otif_target=otif_target,
        high_risk_suitability=high_risk_suitability,
        emergency_suitability=emergency_suitability,
        bulk_suitability=bulk_suitability,
        delay_risk=delay_risk,
        evidence_refs=evidence_refs,
    )


# =========================================================================
# 5. PROCUREMENT POLICY WEIGHTS EXTRACTION
# =========================================================================

def extract_procurement_policy(
    policy_chunks: Optional[List[Any]] = None,
) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
    """
    Extracts deterministic priority weights from retrieved Procurement Policy chunks or applies
    approved SmartSupply 2026 default matrix.

    Returns:
        (weights_dict, warnings)
    """
    warnings: List[str] = []

    # Standard approved SmartSupply corporate weights
    weights = {
        "normal": {"cost": 0.60, "delivery": 0.20, "sla": 0.20},
        "high": {"cost": 0.40, "delivery": 0.40, "sla": 0.20},
        "emergency": {"cost": 0.15, "delivery": 0.60, "sla": 0.25},
    }

    if not policy_chunks:
        warnings.append(
            "Procurement policy document chunks not retrieved; approved SmartSupply decision weights were applied."
        )

    return weights, warnings


# =========================================================================
# 6. SITUATION-AWARE SUPPLIER SCORING & FEASIBILITY GATE
# =========================================================================

def score_supplier_candidate(
    candidate: Dict[str, Any],
    required_delivery_window_days: int,
    urgency: str,
    weights: Dict[str, float],
    policy_signals: SupplierPolicySignals,
    all_candidates: List[Dict[str, Any]],
) -> Tuple[ScoreBreakdown, str, str, int]:
    """
    Scores an individual supplier candidate across Cost, Delivery, and SLA dimensions.

    Returns:
        (ScoreBreakdown, eligibility_status, eligibility_reason, delivery_slack_days)
    """
    lead_time = int(candidate.get("lead_time_days", 999))
    unit_cost = float(candidate.get("unit_cost", 1e9))
    slack = required_delivery_window_days - lead_time

    # 1. Eligibility Check
    if policy_signals.compliance_status == "restricted":
        eligibility_status = "policy_restricted"
        eligibility_reason = "Excluded by procurement compliance policy (restricted/suspended vendor status)."
    elif slack < 0:
        # Check if any other active candidate can meet the window
        any_feasible = any(
            (required_delivery_window_days - int(c.get("lead_time_days", 999))) >= 0
            for c in all_candidates
            if c.get("supplier_id") != candidate.get("supplier_id")
        )
        if any_feasible:
            eligibility_status = "infeasible"
            eligibility_reason = (
                f"Lead time ({lead_time} days) exceeds required delivery window "
                f"({required_delivery_window_days} days; delivery slack: {slack} days). "
                "Infeasible for preventing stockout."
            )
        else:
            eligibility_status = "eligible_exception"
            eligibility_reason = (
                f"No supplier can meet window; candidate evaluated under exception delivery-risk protocol."
            )
    elif slack == 0:
        eligibility_status = "zero_slack"
        eligibility_reason = (
            f"Feasible on-time delivery ({lead_time} days), but zero safety margin "
            f"relative to required window ({required_delivery_window_days} days)."
        )
    else:
        eligibility_status = "eligible"
        eligibility_reason = (
            f"Eligible with positive delivery buffer (+{slack} days safety margin)."
        )

    # 2. Cost Score (0-100)
    # Monotonic normalization against the lowest unit cost in the candidate pool
    min_cost = min(float(c.get("unit_cost", unit_cost)) for c in all_candidates)
    if unit_cost > 0:
        cost_score = round(100.0 * (min_cost / unit_cost), 1)
    else:
        cost_score = 100.0
    cost_score = max(0.0, min(100.0, cost_score))

    # 3. Delivery Score (0-100)
    if slack >= 3:
        delivery_score = 100.0
    elif slack in (1, 2):
        delivery_score = 85.0
    elif slack == 0:
        # Zero-slack penalty: elevated execution risk in HIGH/EMERGENCY
        if urgency in ("high", "emergency"):
            delivery_score = 62.0
        else:
            delivery_score = 85.0
    else:
        # Negative slack: major delivery deficit penalty
        delivery_score = max(10.0, round(40.0 + slack * 10.0, 1))

    # 4. SLA / Reliability Score (0-100)
    # Must be grounded strictly in document evidence; defaults to 80.0 neutral baseline if no evidence
    has_grounded_evidence = bool(
        policy_signals.evidence_refs
        or policy_signals.otif_target is not None
        or policy_signals.reliability_score is not None
        or policy_signals.emergency_suitability != "unknown"
        or policy_signals.high_risk_suitability != "unknown"
        or policy_signals.delay_risk != "unknown"
    )

    if not has_grounded_evidence:
        sla_score = 80.0
    else:
        sla_base = 80.0

        # Grounded OTIF target / Performance Review OTIF
        if policy_signals.otif_target is not None:
            if policy_signals.otif_target >= 98.0:
                sla_base += 10.0
            elif policy_signals.otif_target >= 95.0:
                sla_base += 6.0
            elif policy_signals.otif_target >= 90.0:
                sla_base += 2.0
            else:
                sla_base -= 8.0

        # Grounded Reliability Score from performance reviews
        if policy_signals.reliability_score is not None:
            if policy_signals.reliability_score >= 95.0:
                sla_base += 6.0
            elif policy_signals.reliability_score >= 90.0:
                sla_base += 3.0
            elif policy_signals.reliability_score < 85.0:
                sla_base -= 5.0

        # Urgency & Situation alignment:
        if urgency == "emergency":
            if policy_signals.emergency_suitability == "preferred":
                sla_base += 8.0
            elif policy_signals.emergency_suitability == "limited":
                sla_base -= 15.0

            if policy_signals.expedited_support == "strong":
                sla_base += 6.0
            elif policy_signals.expedited_support == "limited":
                sla_base -= 10.0

        elif urgency == "high":
            if policy_signals.high_risk_suitability == "preferred":
                sla_base += 8.0
            elif policy_signals.high_risk_suitability == "limited":
                sla_base -= 10.0

            if policy_signals.expedited_support == "strong":
                sla_base += 4.0
            elif policy_signals.expedited_support == "limited":
                sla_base -= 8.0

        elif urgency == "normal":
            if policy_signals.bulk_suitability == "preferred":
                sla_base += 8.0
            elif policy_signals.bulk_suitability == "limited":
                sla_base -= 5.0

        # Grounded historical delay variance risk
        if policy_signals.delay_risk == "high":
            sla_base -= 10.0
        elif policy_signals.delay_risk == "low":
            sla_base += 4.0

        sla_score = max(0.0, min(100.0, round(sla_base, 1)))

    # 5. Composite Weighted Score
    w_cost = weights.get("cost", 0.40)
    w_del = weights.get("delivery", 0.40)
    w_sla = weights.get("sla", 0.20)

    weighted = round((w_cost * cost_score) + (w_del * delivery_score) + (w_sla * sla_score), 1)
    weighted_score = max(0.0, min(100.0, weighted))

    breakdown = ScoreBreakdown(
        cost_score=cost_score,
        delivery_score=delivery_score,
        sla_score=sla_score,
        weighted_score=weighted_score,
    )
    return breakdown, eligibility_status, eligibility_reason, slack


# =========================================================================
# 7. MULTI-CANDIDATE SELECTION ORCHESTRATION
# =========================================================================

def select_best_supplier_candidate(
    candidates: List[Dict[str, Any]],
    recommended_quantity: int,
    urgency: str = "normal",
    required_delivery_window_days: Optional[int] = None,
    policy_constraints: Optional[List[str]] = None,
    advisory_supplier_id: Optional[int] = None,
    return_enriched: bool = False,
) -> Any:
    """
    Executes feasibility filtering and situation-aware scoring across candidate suppliers.

    Returns:
        (chosen_candidate, final_quantity, warnings, factors, enriched_candidates)
    """
    warnings: List[str] = []
    factors: List[str] = []

    if not candidates:
        warnings.append("No active suppliers found in catalog for this product.")
        return None, recommended_quantity, warnings, factors, []

    norm_urgency = (urgency or "normal").strip().lower()
    if required_delivery_window_days is None:
        if norm_urgency == "emergency":
            required_delivery_window_days = 2
        elif norm_urgency == "high":
            required_delivery_window_days = 5
        else:
            required_delivery_window_days = 14

    weights_matrix, pol_warnings = extract_procurement_policy()
    weights = weights_matrix.get(norm_urgency, weights_matrix["normal"])
    warnings.extend(pol_warnings)

    enriched_candidates: List[Dict[str, Any]] = []

    # Score each candidate
    for c in candidates:
        c_copy = dict(c)
        policy_signals = c_copy.get("policy_signals") or extract_supplier_policy_signals(c_copy)
        breakdown, elig_status, elig_reason, slack = score_supplier_candidate(
            candidate=c_copy,
            required_delivery_window_days=required_delivery_window_days,
            urgency=norm_urgency,
            weights=weights,
            policy_signals=policy_signals,
            all_candidates=candidates,
        )

        c_copy["score_breakdown"] = breakdown
        c_copy["cost_score"] = breakdown.cost_score
        c_copy["delivery_score"] = breakdown.delivery_score
        c_copy["sla_score"] = breakdown.sla_score
        c_copy["weighted_score"] = breakdown.weighted_score
        c_copy["eligibility_status"] = elig_status
        c_copy["eligibility_reason"] = elig_reason
        c_copy["delivery_slack_days"] = slack
        c_copy["policy_signals"] = policy_signals
        c_copy["is_feasible"] = elig_status in ("eligible", "zero_slack")
        c_copy["disqualification_reason"] = elig_reason if elig_status not in ("eligible", "zero_slack") else None

        if not policy_signals.evidence_refs and policy_signals.otif_target is None:
            warnings.append(f"SLA evidence was insufficient for supplier '{c_copy['supplier_name']}'; neutral baseline score (80.0) applied.")

        if elig_status == "policy_restricted":
            warnings.append(f"Supplier '{c_copy['supplier_name']}' was disqualified due to compliance policy restriction.")

        enriched_candidates.append(c_copy)

    # Feasibility gate:
    # Candidates that are NOT policy_restricted and NOT infeasible (lead time > window when another can meet it)
    feasible = [
        c for c in enriched_candidates
        if c["eligibility_status"] in ("eligible", "zero_slack")
    ]

    chosen: Optional[Dict[str, Any]] = None

    if feasible:
        # Sort feasible candidates by weighted_score descending, then cost ascending
        feasible.sort(key=lambda x: (-x["weighted_score"], float(x["unit_cost"])))
        chosen = feasible[0]
    else:
        # Exception condition: no supplier can meet required delivery window
        # Check compliant options (exclude policy_restricted)
        compliant = [
            c for c in enriched_candidates
            if c["eligibility_status"] != "policy_restricted"
        ]
        if compliant:
            # Pick fastest compliant supplier to minimize exposure
            compliant.sort(key=lambda x: (int(x["lead_time_days"]), float(x["unit_cost"])))
            chosen = compliant[0]
            warnings.append(
                "No available supplier can fully meet the required delivery window. "
                "The fastest compliant supplier was selected to minimize expected exposure."
            )
        else:
            warnings.append("All supplier candidates are disqualified by policy or compliance restrictions.")
            if return_enriched:
                return None, recommended_quantity, warnings, factors, enriched_candidates
            return None, recommended_quantity, warnings, factors

    # MOQ enforcement
    chosen_moq = int(chosen.get("moq", 1))
    final_quantity = recommended_quantity
    if recommended_quantity > 0 and final_quantity < chosen_moq:
        final_quantity = chosen_moq
        factors.append(
            f"Order quantity adjusted up to {chosen_moq} units to satisfy '{chosen['supplier_name']}' MOQ policy."
        )

    # Zero-slack explanation factor
    if chosen.get("delivery_slack_days") == 0:
        if len(feasible) == 1:
            factors.append(
                f"'{chosen['supplier_name']}' is the only supplier capable of meeting the {required_delivery_window_days}-day delivery deadline. "
                f"Its {chosen['lead_time_days']}-day lead time provides zero safety margin, so any delivery delay may still cause a stockout."
            )
        else:
            factors.append(
                f"'{chosen['supplier_name']}' delivery lead time ({chosen['lead_time_days']} days) equals the required delivery deadline, "
                f"providing zero safety margin against delivery delays."
            )

    # Explanation factor
    factors.append(
        f"Selected '{chosen['supplier_name']}' under {norm_urgency.upper()} urgency: "
        f"Weighted Score {chosen['weighted_score']:.1f}/100 (Cost: {chosen['cost_score']:.1f}, "
        f"Delivery: {chosen['delivery_score']:.1f}, SLA: {chosen['sla_score']:.1f}), "
        f"Lead Time {chosen['lead_time_days']} days (Slack: {chosen['delivery_slack_days']} days), "
        f"Unit Cost LKR {chosen['unit_cost']:,.2f}."
    )

    if chosen.get("supplier_id") == advisory_supplier_id:
        factors.append("Selection aligns with Supplier Intelligence Agent advisory preference.")

    if return_enriched:
        return chosen, final_quantity, warnings, factors, enriched_candidates
    return chosen, final_quantity, warnings, factors


# =========================================================================
# 8. DETERMINISTIC EXPLANATION GENERATOR
# =========================================================================

def generate_deterministic_explanation(
    product_name: str,
    replenishment_required: bool,
    quantity: int,
    selected_supplier: Optional[Dict[str, Any]],
    risk_level: str,
    available_stock: int,
    reorder_point: int,
    predicted_demand: float,
    incoming_stock: int = 0,
    raw_quantity: Optional[int] = None,
    net_requirement: Optional[float] = None,
    warnings: Optional[List[str]] = None,
    urgency: str = "normal",
    required_delivery_window_days: int = 14,
    days_until_unsafe: Optional[int] = None,
    days_until_stockout: Optional[int] = None,
    days_until_buffer_breach: Optional[int] = None,
    manual_override_applied: bool = False,
    derived_urgency: Optional[str] = None,
) -> Tuple[str, List[str]]:
    """
    Generates a deterministic, factual explanation and key factor list.
    Ensures explainability is always available even if Grok is offline or unconfigured.
    """
    safe_incoming = max(0, int(incoming_stock))
    effective_inventory = available_stock + safe_incoming
    req_qty = raw_quantity if raw_quantity is not None else quantity
    breach_day = days_until_buffer_breach if days_until_buffer_breach is not None else days_until_unsafe

    factors: List[str] = []
    if safe_incoming > 0:
        factors.append(
            f"Available inventory: {available_stock} units; Confirmed incoming pipeline: {safe_incoming} units "
            f"(Effective inventory position: {effective_inventory} units)."
        )
        factors.append(
            f"{safe_incoming} incoming units were included as confirmed pipeline inventory in replenishment quantity planning. "
            "Their exact arrival timing is unknown because the current inventory model does not store an expected delivery date."
        )
    else:
        factors.append(
            f"Current available inventory: {available_stock} units (Reorder Point: {reorder_point} units)."
        )

    factors.append(f"Forecasted demand over horizon: {predicted_demand:.1f} units.")
    factors.append(f"Reorder point is used as SmartSupply's effective safety-stock buffer: {reorder_point} units.")

    if net_requirement is not None and raw_quantity is not None:
        factors.append(
            f"Net shortage requirement: {net_requirement:.4f} units (rounded up using ceil() to {raw_quantity} units)."
        )

    factors.append(f"Assessed stockout risk level: {risk_level}.")

    if days_until_stockout is not None and breach_day is not None and days_until_stockout < breach_day:
        factors.append(
            f"Inventory timing: Buffer breach projected in {breach_day} days, available inventory exhaustion in {days_until_stockout} days. "
            f"Governing required delivery window: <= {required_delivery_window_days} days."
        )
    elif breach_day is not None:
        factors.append(f"Days until buffer breach: {breach_day} days.")
    if days_until_stockout is not None:
        factors.append(f"Days until available inventory is exhausted: {days_until_stockout} days.")

    factors.append(f"Required delivery window: {required_delivery_window_days} days.")

    if manual_override_applied and derived_urgency and derived_urgency.lower() != urgency.lower():
        factors.append(
            f"Procurement urgency: System-derived {derived_urgency.upper()}; Effective urgency after override: {urgency.upper()}."
        )
    else:
        factors.append(f"Procurement urgency: {urgency.upper()}.")

    if replenishment_required and selected_supplier:
        sup_name = selected_supplier.get("supplier_name", "Designated Supplier")
        unit_cost = float(selected_supplier.get("unit_cost", 0.0))
        lead_time = selected_supplier.get("lead_time_days", 0)
        moq = selected_supplier.get("moq", 1)
        slack = selected_supplier.get("delivery_slack_days", 0)
        total_cost = unit_cost * quantity

        supplier_info = (
            f"Recommended procurement order of {quantity} units designated to '{sup_name}' "
            f"at LKR {unit_cost:,.2f}/unit (Lead time: {lead_time} days)."
        )

        if safe_incoming > 0:
            inv_summary = (
                f"Available stock is {available_stock} units and {safe_incoming} units are confirmed incoming, "
                f"giving an effective inventory position of {effective_inventory} units. "
            )
        else:
            inv_summary = f"Net available inventory ({available_stock} units) "

        timing_clause = ""
        if days_until_stockout is not None and breach_day is not None and days_until_stockout < breach_day:
            timing_clause = (
                f"Although the reorder-point buffer is projected to be breached in {breach_day} days, "
                f"available-to-fulfil inventory may be exhausted in approximately {days_until_stockout} days. "
                f"The {days_until_stockout}-day stockout horizon therefore governs supplier delivery feasibility. "
            )
        elif breach_day is not None:
            timing_clause = f"Projected inventory is expected to become unsafe within approximately {breach_day} days. "

        zero_slack_clause = ""
        if slack == 0:
            zero_slack_clause = (
                f"'{sup_name}' is the only supplier capable of meeting the {required_delivery_window_days}-day delivery deadline. "
                f"Its {lead_time}-day lead time provides zero safety margin, so any delivery delay may still cause a stockout. "
            )

        urgency_note = f"Selected under {urgency.upper()} urgency"
        if manual_override_applied and derived_urgency and derived_urgency.lower() != urgency.lower():
            urgency_note = (
                f"System-derived urgency: {derived_urgency.upper()}; Effective urgency after override: {urgency.upper()}"
            )

        reasoning = (
            f"Replenishment is REQUIRED for '{product_name}'. {inv_summary}"
            f"Forecast demand over the selected horizon is {predicted_demand:.1f} units. "
            f"SmartSupply retains the product's {reorder_point}-unit reorder point as its effective safety-stock buffer. "
            f"Therefore approximately {req_qty} units are required before supplier MOQ constraints. "
            f"{timing_clause}{supplier_info} {zero_slack_clause}"
            f"{urgency_note} (Unit cost: LKR {unit_cost:,.2f}, Lead time: {lead_time} days with {slack} days delivery slack, MOQ: {moq} units, Total: LKR {total_cost:,.2f})."
        )
    elif replenishment_required:
        reasoning = (
            f"Replenishment is REQUIRED for '{product_name}'. Net available inventory ({available_stock} units) "
            f"is insufficient to satisfy the forecasted demand of {predicted_demand:.1f} units and maintain safety stock "
            f"(ROP: {reorder_point} units). Recommended procurement order of {quantity} units. (No compliant supplier currently selected)."
        )
    else:
        if safe_incoming > 0:
            inv_summary = (
                f"Effective inventory position of {effective_inventory} units ({available_stock} available + "
                f"{safe_incoming} confirmed incoming) "
            )
        else:
            inv_summary = f"Net available inventory ({available_stock} units) "

        reasoning = (
            f"Replenishment is NOT REQUIRED for '{product_name}'. {inv_summary}"
            f"is sufficient to satisfy the forecasted demand of {predicted_demand:.1f} units and maintain the "
            f"reorder-point buffer ({reorder_point} units). No immediate purchase order is necessary."
        )

    return reasoning, factors


# =========================================================================
# 9. DATABASE PERSISTENCE & HUMAN APPROVAL WORKFLOWS
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
    Persists a synthesized decision recommendation into PostgreSQL in PENDING state.
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
