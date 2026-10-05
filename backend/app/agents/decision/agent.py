"""
Replenishment Decision Agent (Developer 4).
Orchestrates inputs from:
1. Inventory Monitoring Agent (Developer 1)
2. Demand & Risk Analysis Agent (Developer 2)
3. Supplier Intelligence Agent (Developer 3)

Produces three core decisions:
1. Replenishment Required (YES / NO)
2. Recommended Order Quantity (strictly >= 0)
3. Recommended Supplier (compliant with policy, delivery window, and MOQ)

Automatically derives:
- Required Delivery Window (days until unsafe stock breach)
- Procurement Urgency (Normal, High, Emergency)
- Delivery Slack for all candidates
- Grounded SLA signals and situation-aware scoring across Cost, Delivery, and SLA

Provides explainable reasoning powered by Grok LLM with Responsible AI safeguards
and deterministic fallback resilience.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.inventory.agent import InventoryMonitoringAgent
from app.agents.demand.agent import DemandRiskAgent
from app.agents.supplier_procurement_agent import SupplierProcurementAgent
from app.core.config import settings
from app.core.llm_provider import (
    BaseLLMProvider,
    LLMProviderError,
    get_grok_provider,
)
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.schemas.decision import (
    ApprovalStatus,
    DecisionRecommendationRequest,
    DecisionRecommendationResponse,
    DemandSnapshot,
    DetectedProcurementCondition,
    InventorySnapshot,
    ScoreBreakdown,
    SelectedSupplierInfo,
    SupplierCandidateOption,
    SupplierPolicySignals,
)
from app.schemas.document_processing import DocumentSearchResult
from app.schemas.inventory import InventoryMonitoringItem
from app.schemas.supplier_agent import SupplierAgentRequest
from app.services.decision_service import (
    calculate_replenishment_shortage,
    derive_delivery_window_and_timing,
    derive_procurement_urgency,
    generate_deterministic_explanation,
    select_best_supplier_candidate,
)
from app.services.demand_integration_service import (
    DemandIntegrationError,
    NoSalesHistoryError,
    analyze_product_demand_from_db,
)
from app.services.inventory_service import get_inventory_by_product
from app.services.product_service import ProductNotFoundError, get_product

logger = logging.getLogger(__name__)


GROK_SYSTEM_PROMPT = """You are the SmartSupply Replenishment Decision Support Assistant (Member 4).
Your role is to synthesize multi-agent supply chain intelligence and explain the final replenishment recommendation.

CRITICAL RESPONSIBLE AI DIRECTIVES & OPERATIONAL BOUNDARIES:
1. STRICT CONTEXT GROUNDING: You must ONLY use the supplied factual context (Inventory, Demand, Supplier, and Policy).
2. NEVER HALLUCINATE: Do NOT invent, assume, or fabricate inventory balances, sales demand, supplier names, prices, or company policies.
3. IMMUTABLE DETERMINISTIC CALCULATIONS: You MUST NOT alter, override, or recalculate numerical values (order quantity, unit costs, stock levels, delivery windows, delivery slack, scores). All operational numbers provided in CALCULATED DECISION are final and authoritative.
4. POLICY COMPLIANCE & TERMINOLOGY: Mandatory corporate procurement and inventory policies cannot be bypassed. Reorder point is used as SmartSupply's effective safety-stock buffer (not statistically calculated).
5. ADVISORY NATURE: You are a decision-support advisory system assisting human procurement managers. You do NOT have autonomous purchasing authority. Recommendations require human review.
6. STRUCTURED EXPLAINABILITY (MANDATORY FORMAT):
Your "reasoning" MUST be organized into these clearly labeled sections using bold headings or bullet points so users immediately understand the inventory breakdown, how the stockout occurs, and why the action is required:
- **1. Current Inventory Position:** State exact available-to-fulfil stock (on-hand minus reserved), confirmed incoming pipeline, effective inventory position, and Reorder Point (ROP) safety-stock buffer.
- **2. Demand Forecast & Stockout Mechanism:** Explain clearly HOW and WHY the stockout occurs. State the forecasted demand over the horizon and expected lead-time demand. State the exact projected stockout date and days remaining until available stock is exhausted. Contrast this with the ROP buffer breach day. Explicitly explain that while incoming units exist in the pipeline, their exact arrival date is unconfirmed, meaning available shelf inventory will be exhausted first unless order delivery arrives in time.
- **3. Replenishment Order Sizing & Urgency:** State the net shortage requirement, the authoritative recommended order quantity (accounting for supplier MOQ), and explain why the detected urgency tier was triggered.
- **4. Supplier Selection & Delivery Feasibility:** State the designated supplier, lead time, delivery slack, unit cost, and total spend. Explain why this supplier was chosen (e.g. delivery speed satisfies delivery window) and why slower candidates were disqualified.
7. MISSING DATA TRANSPARENCY & INCOMING STOCK: When incoming stock is present, note that it is included in replenishment quantity planning as confirmed pipeline inventory, but its exact arrival timing is unknown because the inventory model does not store an expected delivery date. NEVER claim or imply that incoming stock arrives on Day 3 or any other specific day.
8. EXACT URGENCY WORDING: Use the exact effective urgency (e.g. "Under EMERGENCY urgency..." or "Under HIGH urgency..."). NEVER combine labels like "EMERGENCY / HIGH". If a manual override is present, state both clearly: "System-derived urgency: HIGH; Effective urgency after override: EMERGENCY".
9. TIMING HORIZON CONSISTENCY: When available inventory exhaustion occurs earlier than reorder-point buffer breach, explain: "Although the reorder-point buffer is projected to be breached in X days, available-to-fulfil inventory may be exhausted in approximately Y days. The Y-day stockout horizon therefore governs supplier delivery feasibility."
10. ZERO DELIVERY SLACK: Zero delivery slack (0 days) is feasible but critical, not comfortable. State: "Digital Distribution is the only supplier capable of meeting the 2-day delivery deadline. Its 2-day lead time provides zero safety margin, so any delivery delay may still cause a stockout."

OUTPUT FORMAT:
You MUST respond with valid JSON strictly conforming to this schema:
{
  "reasoning": "<The structured multi-section explanation formatted in clear sections 1 to 4>",
  "factors": [
    "<Key quantitative, delivery, or policy factor 1>",
    "<Key quantitative, delivery, or policy factor 2>"
  ],
  "confidence": <float between 0.0 and 1.0 indicating synthesis confidence>
}
"""


class DecisionAgent(BaseAgent):
    """
    Replenishment Decision Agent (Developer 4).
    Coordinates the multi-agent pipeline and synthesizes the final explainable recommendation.
    """

    def __init__(
        self,
        agent_name: str = "replenishment_decision_agent",
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        super().__init__(agent_name=agent_name)
        self.llm_provider = llm_provider

    def _get_provider(self) -> BaseLLMProvider:
        return self.llm_provider or get_grok_provider()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the agent reasoning/processing loop implementing BaseAgent.run().

        Supported context parameters:
        - {"db": Session, "product_id": int, ...}
        - {"db": Session, "request": DecisionRecommendationRequest}
        """
        db: Optional[Session] = context.get("db")
        if db is None:
            return {
                "status": "error",
                "agent": self.agent_name,
                "message": "Missing required 'db' Session in agent context.",
            }

        product_id = context.get("product_id")
        sku = context.get("sku")
        forecast_horizon_days = context.get("forecast_horizon_days", 14)
        lead_time_days = context.get("lead_time_days")
        urgency_override = context.get("urgency_override")
        urgency = context.get("urgency")

        request = DecisionRecommendationRequest(
            product_id=product_id,
            sku=sku,
            forecast_horizon_days=forecast_horizon_days,
            lead_time_days=lead_time_days,
            urgency_override=urgency_override,
            urgency=urgency,
        )

        try:
            response = self.generate_recommendation(db=db, request=request)
            return {
                "status": "success",
                "agent": self.agent_name,
                "recommendation": response.model_dump(),
            }
        except Exception as exc:
            logger.error("Error executing DecisionAgent.run: %s", exc, exc_info=True)
            return {
                "status": "error",
                "agent": self.agent_name,
                "message": str(exc),
            }

    def generate_recommendation(
        self,
        db: Session,
        request: DecisionRecommendationRequest,
    ) -> DecisionRecommendationResponse:
        """
        Orchestrates the end-to-end multi-agent replenishment decision pipeline:
        1. Resolve Product Catalog Entity.
        2. Invoke Member 1: Inventory Monitoring Agent.
        3. Invoke Member 2: Demand & Risk Analysis Agent.
        4. Calculate Deterministic Replenishment Requirement & Raw Order Quantity.
        5. Derive Required Delivery Window & Unsafe Stock Timing.
        6. Automatically Derive Procurement Urgency (or evaluate manual override).
        7. Invoke Member 3: Supplier Intelligence Agent (with ChromaDB document IR).
        8. Apply Feasibility Gate & Situation-Aware Candidate Scoring.
        9. Select Optimal Supplier Candidate & Enforce MOQ.
        10. Synthesize Grounded Explainable Recommendation via Grok LLM (with fallback).
        11. Return validated DecisionRecommendationResponse.
        """
        warnings: List[str] = []
        policy_refs: List[str] = []

        # =========================================================================
        # 1. RESOLVE PRODUCT ENTITY
        # =========================================================================
        product: Optional[Product] = None
        if request.product_id:
            try:
                product = get_product(db, request.product_id)
            except ProductNotFoundError:
                raise ValueError(f"Product with ID {request.product_id} does not exist.")
        elif request.sku:
            product = db.scalar(select(Product).where(Product.sku.ilike(request.sku.strip())))
            if not product:
                raise ValueError(f"Product with SKU '{request.sku}' does not exist.")
        else:
            raise ValueError("Either product_id or sku must be provided.")

        # =========================================================================
        # 2. INVOKE MEMBER 1: INVENTORY MONITORING AGENT
        # =========================================================================
        inventory_agent = InventoryMonitoringAgent()
        inventory_item: Optional[InventoryMonitoringItem] = None

        try:
            inventory_item = inventory_agent.monitor_product(db=db, product_id=product.id)
            available_stock = inventory_item.available_stock
            on_hand = inventory_item.on_hand
            reserved = inventory_item.reserved
            incoming = inventory_item.incoming
            reorder_point = inventory_item.reorder_point
            inv_status = inventory_item.status.value
        except Exception as exc:
            logger.warning("Inventory monitoring agent returned fallback for product %d: %s", product.id, exc)
            warnings.append("Inventory record not found in system; default zero stock assumed.")
            available_stock = 0
            on_hand = 0
            reserved = 0
            incoming = 0
            reorder_point = product.reorder_point or 0
            inv_status = "out_of_stock"

        if incoming > 0:
            warnings.append(
                f"{incoming} incoming units were included as confirmed pipeline inventory in replenishment quantity planning. "
                "The current inventory model does not store expected arrival dates."
            )

        inventory_snapshot = InventorySnapshot(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            on_hand=on_hand,
            reserved=reserved,
            incoming=incoming,
            available_stock=available_stock,
            effective_inventory=available_stock + incoming,
            reorder_point=reorder_point,
            status=inv_status,
        )

        # =========================================================================
        # 3. INVOKE MEMBER 2: DEMAND & RISK ANALYSIS AGENT
        # =========================================================================
        forecast_horizon = request.forecast_horizon_days or 14
        lead_time = request.lead_time_days or 3
        predicted_demand = 0.0
        lead_time_demand = 0.0
        demand_risk_level = "LOW"
        projected_stockout_date = None
        selected_forecast_model = None
        daily_forecast_points = []

        try:
            demand_output = analyze_product_demand_from_db(
                db=db,
                product_id=product.id,
                forecast_horizon_days=forecast_horizon,
                lead_time_days=min(lead_time, forecast_horizon),
            )
            predicted_demand = float(demand_output.get("total_forecasted_demand", 0.0))
            stockout_risk_data = demand_output.get("stockout_risk", {})
            lead_time_demand = float(stockout_risk_data.get("expected_demand_over_lead_time", 0.0))
            demand_risk_level = str(stockout_risk_data.get("risk_level", "LOW")).upper()
            projected_stockout_date = stockout_risk_data.get("projected_stockout_date")
            eval_metrics = demand_output.get("evaluation_metrics", {})
            selected_forecast_model = eval_metrics.get("selected_model")
            daily_forecast_points = demand_output.get("daily_forecasts", [])
        except NoSalesHistoryError:
            warnings.append(
                "No historical sales data found for demand forecasting. "
                "Replenishment evaluated strictly against inventory reorder point."
            )
            predicted_demand = 0.0
            demand_risk_level = "HIGH" if available_stock <= reorder_point else "LOW"
        except Exception as exc:
            logger.warning("Demand agent execution failed for product %d: %s", product.id, exc)
            warnings.append(f"Demand forecasting unavailable ({exc.__class__.__name__}); defaulting demand to 0.")
            predicted_demand = 0.0
            demand_risk_level = "HIGH" if available_stock <= reorder_point else "LOW"

        demand_snapshot = DemandSnapshot(
            product_id=product.id,
            forecast_horizon_days=forecast_horizon,
            total_forecasted_demand=round(predicted_demand, 2),
            lead_time_days=lead_time,
            expected_demand_over_lead_time=round(lead_time_demand, 2),
            risk_level=demand_risk_level,
            projected_stockout_date=projected_stockout_date,
            selected_model=selected_forecast_model,
        )

        # =========================================================================
        # 4. DETERMINISTIC REPLENISHMENT SHORTAGE CALCULATION
        # =========================================================================
        replenishment_required, raw_quantity, shortage_metrics = calculate_replenishment_shortage(
            available_stock=available_stock,
            reorder_point=reorder_point,
            predicted_demand=predicted_demand,
            incoming_stock=incoming,
        )

        # =========================================================================
        # 5. DERIVE REQUIRED DELIVERY WINDOW & UNCACHED TIMING
        # =========================================================================
        timing_info = derive_delivery_window_and_timing(
            available_stock=available_stock,
            reorder_point=reorder_point,
            daily_forecasts=daily_forecast_points,
            forecast_horizon_days=forecast_horizon,
            incoming_stock=incoming,
        )
        days_until_buffer_breach = timing_info.get("days_until_buffer_breach", timing_info.get("days_until_unsafe"))
        days_until_unsafe = timing_info["days_until_unsafe"]
        days_until_stockout = timing_info["days_until_stockout"]
        required_delivery_window_days = timing_info["required_delivery_window_days"]

        # Gather active supplier lead times for this product
        offers_db = db.scalars(
            select(ProductSupplier).where(ProductSupplier.product_id == product.id, ProductSupplier.is_active == True)
        ).all()
        active_lead_times = [int(o.lead_time_days) for o in offers_db] or [3]

        # =========================================================================
        # 6. AUTOMATIC PROCUREMENT URGENCY DERIVATION & MANUAL OVERRIDE AUDIT
        # =========================================================================
        derived_urgency, condition_reason = derive_procurement_urgency(
            replenishment_required=replenishment_required,
            stockout_risk_level=demand_risk_level,
            days_until_unsafe=days_until_unsafe,
            days_until_stockout=days_until_stockout,
            required_delivery_window_days=required_delivery_window_days,
            active_lead_times=active_lead_times,
            available_stock=available_stock,
            reorder_point=reorder_point,
            days_until_buffer_breach=days_until_buffer_breach,
        )

        manual_override = request.urgency_override or (request.urgency if request.urgency and request.urgency != "auto" else None)
        manual_override_applied = False
        if manual_override and manual_override in ("normal", "high", "emergency"):
            effective_urgency = manual_override
            if manual_override != derived_urgency:
                manual_override_applied = True
                warnings.append(
                    f"System-derived urgency was {derived_urgency.upper()}, but {manual_override.upper()} was manually selected."
                )
        else:
            effective_urgency = derived_urgency

        detected_condition = DetectedProcurementCondition(
            stockout_risk=demand_risk_level,
            procurement_urgency=derived_urgency,
            effective_urgency=effective_urgency,
            manual_override_applied=manual_override_applied,
            required_delivery_window_days=required_delivery_window_days,
            days_until_buffer_breach=days_until_buffer_breach,
            days_until_unsafe=days_until_unsafe,
            days_until_stockout=days_until_stockout,
            reason=condition_reason,
            risk_level=demand_risk_level,
            derived_urgency=derived_urgency,
            condition_reason=condition_reason,
        )

        # =========================================================================
        # 7. INVOKE MEMBER 3: SUPPLIER INTELLIGENCE AGENT
        # =========================================================================
        supplier_agent = SupplierProcurementAgent()
        advisory_supplier_id: Optional[int] = None
        raw_candidates: List[Dict[str, Any]] = []

        try:
            supp_request = SupplierAgentRequest(
                product_id=product.id,
                requested_quantity=raw_quantity if raw_quantity > 0 else None,
                urgency=effective_urgency,
                stockout_risk=demand_risk_level,
            )
            supp_response = supplier_agent.assess_suppliers(request=supp_request, db=db)

            if supp_response.advisory_supplier:
                advisory_supplier_id = supp_response.advisory_supplier.supplier_id

            if supp_response.policy_constraints:
                policy_refs.extend(supp_response.policy_constraints)
            if supp_response.warnings:
                warnings.extend(supp_response.warnings)

            for c in supp_response.candidate_assessments:
                c_dict = c.model_dump()
                # Ensure evidence objects are preserved
                c_dict["evidence"] = [
                    DocumentSearchResult.model_validate(ev) if isinstance(ev, dict) else ev
                    for ev in (c.evidence or [])
                ]
                raw_candidates.append(c_dict)
        except Exception as exc:
            logger.warning("Supplier procurement agent call failed: %s", exc)
            warnings.append(f"Supplier intelligence evaluation unavailable: {str(exc)}")

        # Fallback to direct ProductSupplier query if candidate list is empty
        if not raw_candidates:
            for o in offers_db:
                s_name = o.supplier.name if o.supplier else f"Supplier {o.supplier_id}"
                c_dict = {
                    "supplier_id": o.supplier_id,
                    "supplier_code": o.supplier.supplier_code if o.supplier else None,
                    "supplier_name": s_name,
                    "unit_cost": float(o.unit_cost),
                    "moq": o.moq,
                    "lead_time_days": o.lead_time_days,
                    "meets_moq": raw_quantity >= o.moq if raw_quantity > 0 else True,
                    "estimated_cost": float(o.unit_cost) * raw_quantity if raw_quantity > 0 else 0.0,
                    "advantages": [f"Unit cost: LKR {float(o.unit_cost):,.2f}", f"Lead time: {o.lead_time_days} days"],
                    "risks": [],
                    "evidence": [],
                }
                raw_candidates.append(c_dict)

        # =========================================================================
        # 8. SITUATION-AWARE SUPPLIER SCORING & SELECTION
        # =========================================================================
        chosen_candidate, final_quantity, sup_warnings, sup_factors, enriched_candidates = select_best_supplier_candidate(
            candidates=raw_candidates,
            recommended_quantity=raw_quantity,
            urgency=effective_urgency,
            required_delivery_window_days=required_delivery_window_days,
            policy_constraints=policy_refs,
            advisory_supplier_id=advisory_supplier_id,
            return_enriched=True,
        )

        warnings.extend(sup_warnings)

        # Build supplier options schema list
        supplier_options: List[SupplierCandidateOption] = []
        for ec in enriched_candidates:
            supplier_options.append(SupplierCandidateOption(
                supplier_id=ec["supplier_id"],
                supplier_code=ec.get("supplier_code"),
                supplier_name=ec["supplier_name"],
                unit_cost=ec["unit_cost"],
                moq=ec["moq"],
                lead_time_days=ec["lead_time_days"],
                meets_moq=ec.get("meets_moq"),
                estimated_cost=ec.get("estimated_cost"),
                advantages=ec.get("advantages") or [],
                risks=ec.get("risks") or [],
                evidence=[
                    DocumentSearchResult.model_validate(ev) if isinstance(ev, dict) else ev
                    for ev in (ec.get("evidence") or [])
                ],
                delivery_slack_days=ec.get("delivery_slack_days"),
                eligibility_status=ec.get("eligibility_status"),
                eligibility_reason=ec.get("eligibility_reason"),
                cost_score=ec.get("cost_score"),
                delivery_score=ec.get("delivery_score"),
                sla_score=ec.get("sla_score"),
                weighted_score=ec.get("weighted_score"),
                score_breakdown=ec.get("score_breakdown"),
                policy_signals=ec.get("policy_signals"),
                score=round(float(ec.get("weighted_score", 0.0)) / 100.0, 3) if ec.get("weighted_score") is not None else None,
                signals=ec.get("policy_signals"),
                is_feasible=ec.get("is_feasible", True),
                disqualification_reason=ec.get("disqualification_reason"),
            ))

        # Safeguard: never negative quantity
        final_quantity = max(0, final_quantity)
        if not replenishment_required:
            final_quantity = 0

        # Construct selected supplier summary
        selected_supplier_info: Optional[SelectedSupplierInfo] = None
        if chosen_candidate and replenishment_required:
            est_total = float(chosen_candidate["unit_cost"]) * final_quantity
            selection_reason = (
                f"Selected under {effective_urgency.upper()} urgency: "
                f"Weighted score {chosen_candidate.get('weighted_score', 0.0):.1f}/100 "
                f"(Cost: {chosen_candidate.get('cost_score', 0.0):.1f}, Delivery: {chosen_candidate.get('delivery_score', 0.0):.1f}, SLA: {chosen_candidate.get('sla_score', 0.0):.1f}), "
                f"Unit cost: LKR {chosen_candidate['unit_cost']:,.2f}, Lead time: {chosen_candidate['lead_time_days']} days "
                f"(Slack: {chosen_candidate.get('delivery_slack_days', 0)} days), MOQ: {chosen_candidate['moq']} units."
            )
            selected_supplier_info = SelectedSupplierInfo(
                supplier_id=chosen_candidate["supplier_id"],
                supplier_code=chosen_candidate.get("supplier_code"),
                supplier_name=chosen_candidate["supplier_name"],
                unit_cost=chosen_candidate["unit_cost"],
                moq=chosen_candidate["moq"],
                lead_time_days=chosen_candidate["lead_time_days"],
                estimated_total_cost=round(est_total, 2),
                selection_reason=selection_reason,
                advantages=list(chosen_candidate.get("advantages") or []),
                risks=list(chosen_candidate.get("risks") or []),
                evidence=[
                    DocumentSearchResult.model_validate(ev) if isinstance(ev, dict) else ev
                    for ev in (chosen_candidate.get("evidence") or [])
                ],
                delivery_slack_days=chosen_candidate.get("delivery_slack_days"),
                eligibility_status=chosen_candidate.get("eligibility_status"),
                eligibility_reason=chosen_candidate.get("eligibility_reason"),
                score_breakdown=chosen_candidate.get("score_breakdown"),
                policy_signals=chosen_candidate.get("policy_signals"),
            )

        # Composite risk level
        overall_risk_level = "LOW"
        if available_stock == 0:
            overall_risk_level = "CRITICAL"
        elif available_stock <= reorder_point or demand_risk_level == "HIGH":
            overall_risk_level = "HIGH"
        elif demand_risk_level == "MEDIUM" or available_stock <= reorder_point * 1.5:
            overall_risk_level = "MEDIUM"

        if not policy_refs:
            policy_refs.append(
                "SmartSupply Procurement Policy 2026 (Priority Weighting Matrix: Normal 60/20/20, High 40/40/20, Emergency 15/60/25)"
            )
            policy_refs.append(
                "SmartSupply Inventory Replenishment Policy 2026 (Reorder Point used as effective safety-stock buffer)"
            )

        # =========================================================================
        # 9. GROK LLM SYNTHESIS & EXPLAINABILITY (WITH SAFEGUARDED FALLBACK)
        # =========================================================================
        reasoning, factors, confidence = self._synthesize_explanation_with_grok(
            product=product,
            replenishment_required=replenishment_required,
            raw_quantity=raw_quantity,
            final_quantity=final_quantity,
            net_requirement=shortage_metrics.get("net_requirement"),
            selected_supplier=chosen_candidate,
            risk_level=overall_risk_level,
            inventory_snapshot=inventory_snapshot,
            demand_snapshot=demand_snapshot,
            supplier_candidates=enriched_candidates,
            policy_refs=policy_refs,
            warnings=warnings,
            deterministic_factors=sup_factors,
            urgency=effective_urgency,
            required_delivery_window_days=required_delivery_window_days,
            days_until_unsafe=days_until_unsafe,
            days_until_stockout=days_until_stockout,
            days_until_buffer_breach=days_until_buffer_breach,
            manual_override_applied=manual_override_applied,
            derived_urgency=derived_urgency,
        )

        # Suppress any false missing SLA/performance documentation warning if evidence exists
        final_warnings: List[str] = []
        for w in list(dict.fromkeys(warnings)):
            w_lower = w.lower()
            is_missing_doc = any(k in w_lower for k in ["lack", "missing", "insufficient", "no sla", "without sla", "no performance", "no documentation"]) and any(k in w_lower for k in ["sla", "performance", "documentation", "evidence", "document"])
            if is_missing_doc:
                suppress = False
                if chosen_candidate:
                    c_id = chosen_candidate.get("supplier_id")
                    c_name = (chosen_candidate.get("supplier_name") or "").lower()
                    c_ev = chosen_candidate.get("evidence") or []
                    if len(c_ev) > 0 and ((c_id and str(c_id) in w) or (c_name and c_name in w_lower) or "supplier" in w_lower):
                        suppress = True
                for cand in raw_candidates:
                    s_id = cand.get("supplier_id")
                    s_name = (cand.get("supplier_name") or "").lower()
                    s_ev = cand.get("evidence") or []
                    if len(s_ev) > 0 and ((s_id and str(s_id) in w) or (s_name and s_name in w_lower)):
                        suppress = True
                        break
                if suppress:
                    continue
            final_warnings.append(w)

        return DecisionRecommendationResponse(
            id=None,
            product_id=product.id,
            sku=product.sku,
            product_name=product.name,
            replenishment_required=replenishment_required,
            recommended_order_quantity=final_quantity,
            selected_supplier=selected_supplier_info,
            derived_urgency=derived_urgency,
            effective_urgency=effective_urgency,
            manual_urgency_override=manual_override if manual_override_applied else None,
            manual_override_applied=manual_override_applied,
            required_delivery_window_days=required_delivery_window_days,
            days_until_buffer_breach=days_until_buffer_breach,
            days_until_unsafe=days_until_unsafe,
            days_until_stockout=days_until_stockout,
            detected_condition=detected_condition,
            risk_level=overall_risk_level,
            reasoning=reasoning,
            factors=factors,
            warnings=final_warnings,
            policy_references=list(dict.fromkeys(policy_refs)),
            confidence=confidence,
            approval_status=ApprovalStatus.PENDING,
            inventory_context=inventory_snapshot,
            demand_context=demand_snapshot,
            supplier_options=supplier_options,
        )

    def _synthesize_explanation_with_grok(
        self,
        product: Product,
        replenishment_required: bool,
        raw_quantity: int,
        final_quantity: int,
        net_requirement: Optional[float],
        selected_supplier: Optional[Dict[str, Any]],
        risk_level: str,
        inventory_snapshot: InventorySnapshot,
        demand_snapshot: DemandSnapshot,
        supplier_candidates: List[Dict[str, Any]],
        policy_refs: List[str],
        warnings: List[str],
        deterministic_factors: List[str],
        urgency: str = "normal",
        required_delivery_window_days: int = 14,
        days_until_unsafe: Optional[int] = None,
        days_until_stockout: Optional[int] = None,
        days_until_buffer_breach: Optional[int] = None,
        manual_override_applied: bool = False,
        derived_urgency: Optional[str] = None,
    ) -> Tuple[str, List[str], float]:
        """
        Attempts Grok LLM synthesis with grounded context and strict validation.
        Falls back to deterministic explanation if Grok is offline, times out, or fails.
        """
        provider = self._get_provider()
        effective_inventory = inventory_snapshot.available_stock + inventory_snapshot.incoming
        breach_day = days_until_buffer_breach if days_until_buffer_breach is not None else days_until_unsafe

        user_prompt_data = {
            "target_product": {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
            },
            "inventory_context": {
                "available_stock": inventory_snapshot.available_stock,
                "on_hand": inventory_snapshot.on_hand,
                "reserved": inventory_snapshot.reserved,
                "incoming": inventory_snapshot.incoming,
                "effective_inventory": effective_inventory,
                "reorder_point": inventory_snapshot.reorder_point,
                "effective_safety_stock_buffer": inventory_snapshot.reorder_point,
                "health_status": inventory_snapshot.status,
            },
            "demand_and_risk_context": {
                "forecast_horizon_days": demand_snapshot.forecast_horizon_days,
                "total_forecasted_demand": demand_snapshot.total_forecasted_demand,
                "lead_time_days": demand_snapshot.lead_time_days,
                "expected_demand_over_lead_time": demand_snapshot.expected_demand_over_lead_time,
                "stockout_risk_level": demand_snapshot.risk_level,
                "projected_stockout_date": str(demand_snapshot.projected_stockout_date) if demand_snapshot.projected_stockout_date else None,
                "required_delivery_window_days": required_delivery_window_days,
                "days_until_buffer_breach": breach_day,
                "days_until_stockout": days_until_stockout,
            },
            "procurement_urgency": urgency.upper(),
            "derived_urgency": derived_urgency.upper() if derived_urgency else urgency.upper(),
            "manual_override_applied": manual_override_applied,
            "supplier_candidates_context": [
                {
                    "supplier_id": c.get("supplier_id"),
                    "supplier_name": c.get("supplier_name"),
                    "unit_cost": c.get("unit_cost"),
                    "moq": c.get("moq"),
                    "lead_time_days": c.get("lead_time_days"),
                    "delivery_slack_days": c.get("delivery_slack_days"),
                    "eligibility_status": c.get("eligibility_status"),
                    "weighted_score": c.get("weighted_score"),
                }
                for c in supplier_candidates
            ],
            "policy_context": policy_refs,
            "calculated_deterministic_decision": {
                "replenishment_required": replenishment_required,
                "effective_inventory": effective_inventory,
                "net_requirement": round(net_requirement, 4) if net_requirement is not None else None,
                "raw_order_quantity": raw_quantity,
                "authoritative_order_quantity": final_quantity,
                "selected_supplier": selected_supplier.get("supplier_name") if selected_supplier else "None",
                "calculated_risk_level": risk_level,
            },
        }

        user_prompt = (
            "TASK: Explain the supply-chain replenishment recommendation using ONLY the following grounded context.\n"
            "You MUST format the 'reasoning' into these 4 clear markdown sections:\n"
            "**1. Current Inventory Position:** (Available-to-fulfil stock, on-hand, reserved, incoming pipeline, effective inventory, and ROP safety buffer).\n"
            "**2. Demand Forecast & Stockout Mechanism:** (How and why stockout is happening, customer demand rate, projected stockout date/days, and why incoming pipeline does not arrive in time to stop the initial shelf stockout).\n"
            "**3. Replenishment Order Sizing & Urgency:** (Net shortage, authoritative recommended order quantity, MOQ compliance, and urgency tier reason).\n"
            "**4. Supplier Selection & Delivery Feasibility:** (Designated supplier, lead time vs deadline, delivery slack, unit cost, and why competitors failed).\n"
            "Do not alter the calculated numbers.\n\n"
            f"STRUCTURED CONTEXT:\n{json.dumps(user_prompt_data, indent=2)}\n\n"
            "Respond strictly in the required JSON format."
        )

        try:
            raw_response = provider.generate_text(
                system_prompt=GROK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                timeout=getattr(settings, "LLM_TIMEOUT_SECONDS", 15),
            )
            parsed = self._extract_json(raw_response)
            if parsed and isinstance(parsed, dict) and "reasoning" in parsed:
                grok_reasoning = str(parsed["reasoning"]).strip()
                grok_factors = parsed.get("factors", [])
                if not isinstance(grok_factors, list):
                    grok_factors = [str(grok_factors)]
                confidence = float(parsed.get("confidence", 0.95))

                all_factors = list(dict.fromkeys(deterministic_factors + [str(f) for f in grok_factors]))
                return grok_reasoning, all_factors, confidence

        except LLMProviderError as exc:
            logger.info("Grok provider unavailable or failed (%s). Falling back to deterministic explanation.", exc)
        except Exception as exc:
            logger.warning("Unexpected error during Grok explanation call: %s", exc)

        # Fallback to deterministic explanation
        det_reasoning, det_factors = generate_deterministic_explanation(
            product_name=product.name,
            replenishment_required=replenishment_required,
            quantity=final_quantity,
            selected_supplier=selected_supplier,
            risk_level=risk_level,
            available_stock=inventory_snapshot.available_stock,
            reorder_point=inventory_snapshot.reorder_point,
            predicted_demand=demand_snapshot.total_forecasted_demand,
            incoming_stock=inventory_snapshot.incoming,
            raw_quantity=raw_quantity,
            net_requirement=net_requirement,
            warnings=warnings,
            urgency=urgency,
            required_delivery_window_days=required_delivery_window_days,
            days_until_unsafe=days_until_unsafe,
            days_until_stockout=days_until_stockout,
            days_until_buffer_breach=days_until_buffer_breach,
            manual_override_applied=manual_override_applied,
            derived_urgency=derived_urgency,
        )

        combined_factors = list(dict.fromkeys(deterministic_factors + det_factors))
        return det_reasoning, combined_factors, 0.90

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return None
