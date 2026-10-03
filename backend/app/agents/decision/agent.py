"""
Replenishment Decision Agent (Developer 4).
Orchestrates inputs from:
1. Inventory Monitoring Agent (Developer 1)
2. Demand & Risk Analysis Agent (Developer 2)
3. Supplier Intelligence Agent (Developer 3)

Produces three core decisions:
1. Replenishment Required (YES / NO)
2. Recommended Order Quantity (strictly >= 0)
3. Recommended Supplier (compliant with policy and MOQ)

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
from app.schemas.decision import (
    ApprovalStatus,
    DecisionRecommendationRequest,
    DecisionRecommendationResponse,
    DemandSnapshot,
    InventorySnapshot,
    SelectedSupplierInfo,
    SupplierCandidateOption,
)
from app.schemas.inventory import InventoryMonitoringItem
from app.schemas.supplier_agent import SupplierAgentRequest
from app.services.decision_service import (
    calculate_replenishment_shortage,
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
3. IMMUTABLE DETERMINISTIC CALCULATIONS: You MUST NOT alter, override, or recalculate the numerical values (order quantity, unit costs, stock levels, dates) determined by the deterministic backend logic. All operational numbers provided in CALCULATED DECISION are final and authoritative.
4. POLICY COMPLIANCE: Mandatory corporate procurement and inventory policies cannot be bypassed or overridden.
5. ADVISORY NATURE: You are a decision-support advisory system assisting human procurement managers. You do NOT have autonomous purchasing authority. Recommendations require human review.
6. EXPLAINABILITY: Provide clear, concise, professional business reasoning explaining why replenishment is or is not required, and why the designated supplier was selected.
7. MISSING DATA TRANSPARENCY: If certain information was unavailable, explicitly acknowledge the caveat without speculation.

OUTPUT FORMAT:
You MUST respond with valid JSON strictly conforming to this schema:
{
  "reasoning": "<Concise, professional explanation of the replenishment decision and supplier choice>",
  "factors": [
    "<Key quantitative or policy factor 1>",
    "<Key quantitative or policy factor 2>"
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
        urgency = context.get("urgency", "normal")

        request = DecisionRecommendationRequest(
            product_id=product_id,
            sku=sku,
            forecast_horizon_days=forecast_horizon_days,
            lead_time_days=lead_time_days,
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
        5. Invoke Member 3: Supplier Intelligence Agent.
        6. Apply Deterministic Business Safeguards, Policy Constraints, & Supplier Selection.
        7. Synthesize Grounded Explainable Recommendation via Grok LLM (with fallback).
        8. Return validated DecisionRecommendationResponse.
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

        inventory_snapshot = InventorySnapshot(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            on_hand=on_hand,
            reserved=reserved,
            incoming=incoming,
            available_stock=available_stock,
            reorder_point=reorder_point,
            status=inv_status,
        )

        # =========================================================================
        # 3. INVOKE MEMBER 2: DEMAND & RISK ANALYSIS AGENT
        # =========================================================================
        forecast_horizon = request.forecast_horizon_days or 14
        lead_time = request.lead_time_days or 3  # Initial estimate for lead-time window
        predicted_demand = 0.0
        lead_time_demand = 0.0
        demand_risk_level = "LOW"
        projected_stockout_date = None
        selected_forecast_model = None

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
        )

        # =========================================================================
        # 5. INVOKE MEMBER 3: SUPPLIER INTELLIGENCE AGENT
        # =========================================================================
        supplier_agent = SupplierProcurementAgent()
        supplier_options: List[SupplierCandidateOption] = []
        advisory_supplier_id: Optional[int] = None
        raw_candidates: List[Dict[str, Any]] = []

        try:
            supp_request = SupplierAgentRequest(
                product_id=product.id,
                requested_quantity=raw_quantity if raw_quantity > 0 else None,
                urgency=request.urgency,
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
                raw_candidates.append(c.model_dump())
                supplier_options.append(SupplierCandidateOption(
                    supplier_id=c.supplier_id,
                    supplier_code=c.supplier_code,
                    supplier_name=c.supplier_name,
                    unit_cost=c.unit_cost,
                    moq=c.moq,
                    lead_time_days=c.lead_time_days,
                    meets_moq=c.meets_moq,
                    estimated_cost=c.estimated_cost,
                    advantages=c.advantages,
                    risks=c.risks,
                ))
        except Exception as exc:
            logger.warning("Supplier procurement agent call failed: %s", exc)
            warnings.append(f"Supplier intelligence evaluation unavailable: {str(exc)}")

        # Fallback to direct ProductSupplier query if candidate list is empty
        if not raw_candidates:
            from app.models.product_supplier import ProductSupplier
            offers = db.scalars(
                select(ProductSupplier)
                .where(ProductSupplier.product_id == product.id, ProductSupplier.is_active == True)
            ).all()
            for o in offers:
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
                }
                raw_candidates.append(c_dict)
                supplier_options.append(SupplierCandidateOption(**c_dict))

        # =========================================================================
        # 6. DETERMINISTIC SUPPLIER SELECTION & MOQ ENFORCEMENT
        # =========================================================================
        chosen_candidate, final_quantity, sup_warnings, sup_factors = select_best_supplier_candidate(
            candidates=raw_candidates,
            recommended_quantity=raw_quantity,
            urgency=request.urgency,
            policy_constraints=policy_refs,
            advisory_supplier_id=advisory_supplier_id,
        )

        warnings.extend(sup_warnings)

        # Safeguard: never negative quantity
        final_quantity = max(0, final_quantity)
        if not replenishment_required:
            final_quantity = 0

        # Construct selected supplier summary
        selected_supplier_info: Optional[SelectedSupplierInfo] = None
        if chosen_candidate and replenishment_required:
            est_total = float(chosen_candidate["unit_cost"]) * final_quantity
            selection_reason = (
                f"Selected as the most cost-effective and compliant active supplier "
                f"(Unit cost: LKR {chosen_candidate['unit_cost']:,.2f}, Lead time: {chosen_candidate['lead_time_days']} days, MOQ: {chosen_candidate['moq']})."
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
            )

        # Composite risk level
        overall_risk_level = "LOW"
        if available_stock == 0:
            overall_risk_level = "CRITICAL"
        elif available_stock <= reorder_point or demand_risk_level == "HIGH":
            overall_risk_level = "HIGH"
        elif demand_risk_level == "MEDIUM" or available_stock <= reorder_point * 1.5:
            overall_risk_level = "MEDIUM"

        # Default policy reference if none found
        if not policy_refs:
            policy_refs.append("Standard Corporate Inventory & Procurement Policy (Safety Stock = ROP)")

        # =========================================================================
        # 7. GROK LLM SYNTHESIS & EXPLAINABILITY (WITH SAFEGUARDED FALLBACK)
        # =========================================================================
        reasoning, factors, confidence = self._synthesize_explanation_with_grok(
            product=product,
            replenishment_required=replenishment_required,
            final_quantity=final_quantity,
            selected_supplier=chosen_candidate,
            risk_level=overall_risk_level,
            inventory_snapshot=inventory_snapshot,
            demand_snapshot=demand_snapshot,
            supplier_candidates=raw_candidates,
            policy_refs=policy_refs,
            warnings=warnings,
            deterministic_factors=sup_factors,
        )

        return DecisionRecommendationResponse(
            id=None,
            product_id=product.id,
            sku=product.sku,
            product_name=product.name,
            replenishment_required=replenishment_required,
            recommended_order_quantity=final_quantity,
            selected_supplier=selected_supplier_info,
            risk_level=overall_risk_level,
            reasoning=reasoning,
            factors=factors,
            warnings=list(dict.fromkeys(warnings)),  # Deduplicate while preserving order
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
        final_quantity: int,
        selected_supplier: Optional[Dict[str, Any]],
        risk_level: str,
        inventory_snapshot: InventorySnapshot,
        demand_snapshot: DemandSnapshot,
        supplier_candidates: List[Dict[str, Any]],
        policy_refs: List[str],
        warnings: List[str],
        deterministic_factors: List[str],
    ) -> Tuple[str, List[str], float]:
        """
        Attempts Grok LLM synthesis with grounded context and strict validation.
        Falls back to deterministic explanation if Grok is offline, times out, or fails.
        """
        provider = self._get_provider()

        # Build delimited, untrusted-safe structured context prompt
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
                "reorder_point": inventory_snapshot.reorder_point,
                "health_status": inventory_snapshot.status,
            },
            "demand_and_risk_context": {
                "forecast_horizon_days": demand_snapshot.forecast_horizon_days,
                "total_forecasted_demand": demand_snapshot.total_forecasted_demand,
                "lead_time_days": demand_snapshot.lead_time_days,
                "expected_demand_over_lead_time": demand_snapshot.expected_demand_over_lead_time,
                "stockout_risk_level": demand_snapshot.risk_level,
                "projected_stockout_date": str(demand_snapshot.projected_stockout_date) if demand_snapshot.projected_stockout_date else None,
            },
            "supplier_candidates_context": [
                {
                    "supplier_id": c.get("supplier_id"),
                    "supplier_name": c.get("supplier_name"),
                    "unit_cost": c.get("unit_cost"),
                    "moq": c.get("moq"),
                    "lead_time_days": c.get("lead_time_days"),
                }
                for c in supplier_candidates
            ],
            "policy_context": policy_refs,
            "calculated_deterministic_decision": {
                "replenishment_required": replenishment_required,
                "authoritative_order_quantity": final_quantity,
                "selected_supplier": selected_supplier.get("supplier_name") if selected_supplier else "None",
                "calculated_risk_level": risk_level,
            },
        }

        user_prompt = (
            "TASK: Explain the supply-chain replenishment recommendation using ONLY the following grounded context.\n"
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

                # Combine deterministic factors with Grok factors
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
            warnings=warnings,
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
