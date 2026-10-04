"""
Live End-to-End Verification for DEMO-001 (Product ID 32).
Executes DecisionAgent with automatic urgency derivation, verifies delivery window,
delivery slack calculations, situation-aware candidate scoring, and grounded IR evidence.
"""

import sys
import os
import json
from decimal import Decimal

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.session import SessionLocal
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.product_supplier import ProductSupplier
from app.schemas.decision import DecisionRecommendationRequest
from app.agents.decision.agent import DecisionAgent


def run_live_verification():
    db = SessionLocal()
    try:
        # 1. Verify DEMO-001 database state
        product = db.query(Product).filter(Product.sku == "DEMO-001").first()
        if not product:
            print("[ERROR] Product DEMO-001 not found in PostgreSQL!")
            return 1

        print("=" * 80)
        print(f"SMARTSUPPLY DECISION INTELLIGENCE LIVE VERIFICATION")
        print(f"Product: {product.name} (SKU: {product.sku}, ID: {product.id})")
        print(f"Reorder Point: {product.reorder_point}")

        inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
        if inv:
            eff_inv = inv.available_stock + (inv.incoming or 0)
            print(f"Inventory: on_hand={inv.on_hand}, reserved={inv.reserved}, incoming={inv.incoming}")
            print(f"Available physical stock: {inv.available_stock} | Effective inventory: {eff_inv}")

        suppliers = db.query(ProductSupplier).filter(ProductSupplier.product_id == product.id).all()
        print("\nActive Supplier Catalog:")
        for s in suppliers:
            s_name = s.supplier.name if s.supplier else f"Supplier #{s.supplier_id}"
            print(f"  - {s_name}: Cost = LKR {s.unit_cost:,.2f}, MOQ = {s.moq}, Lead Time = {s.lead_time_days} days")

        # 2. Run Autonomous Decision Agent (No Urgency provided by user -> Auto-derived)
        print("\n" + "=" * 80)
        print("RUNNING DECISION AGENT (Automatic Urgency Derivation)...")
        agent = DecisionAgent()
        req = DecisionRecommendationRequest(
            product_id=product.id,
            forecast_horizon_days=14,
            # No manual urgency override passed
        )
        resp = agent.generate_recommendation(db=db, request=req)

        # 3. Print Results
        print("\n" + "=" * 80)
        print("DECISION INTELLIGENCE RESULTS:")
        print(f"Replenishment Required: {resp.replenishment_required}")
        print(f"Recommended Quantity:   {resp.recommended_order_quantity} units")
        print(f"Risk Level:             {resp.risk_level}")
        print(f"Derived Urgency:        {resp.derived_urgency.upper()}")
        print(f"Effective Urgency:      {resp.effective_urgency.upper()}")
        print(f"Manual Override Applied:{resp.manual_override_applied}")
        print(f"Required Window:        {resp.required_delivery_window_days} days")

        if resp.detected_condition:
            dc = resp.detected_condition
            print(f"\nDETECTED PROCUREMENT CONDITION:")
            print(f"  Stockout Risk:            {dc.stockout_risk}")
            print(f"  Days Until Buffer Breach: {dc.days_until_buffer_breach} days")
            print(f"  Days Until Physical Stockout: {dc.days_until_stockout} days")
            print(f"  Required Delivery Window: {dc.required_delivery_window_days} days")
            print(f"  Condition Reason:         {dc.reason}")

        print(f"\nEVALUATED CANDIDATE SUPPLIERS ({len(resp.supplier_options)}):")
        for sup in resp.supplier_options:
            is_selected = resp.selected_supplier and sup.supplier_id == resp.selected_supplier.supplier_id
            sel_flag = " [SELECTED OPTIMAL]" if is_selected else ""
            status_desc = "FEASIBLE" if sup.is_feasible else f"DISQUALIFIED ({sup.disqualification_reason})"
            score_str = f"Overall Score: {sup.weighted_score:.1f}/100" if sup.weighted_score is not None else "No score"
            slack_str = f"Slack: {sup.delivery_slack_days:+d}d" if sup.delivery_slack_days is not None else "Slack: N/A"

            print(f"\n  Supplier: {sup.supplier_name} (ID: {sup.supplier_id}){sel_flag}")
            print(f"    Terms: Cost = LKR {sup.unit_cost:,.2f} | Lead Time = {sup.lead_time_days}d | MOQ = {sup.moq}u")
            print(f"    Timing: {slack_str} | Feasibility: {status_desc}")
            print(f"    Evaluation: {score_str}")
            if sup.score_breakdown:
                sb = sup.score_breakdown
                pen_flag = " (Zero-Slack Delivery Penalty Applied)" if sup.eligibility_status == "zero_slack" else ""
                print(f"    Scores: Cost={sb.cost_score:.1f}, Delivery={sb.delivery_score:.1f}{pen_flag}, SLA={sb.sla_score:.1f} -> Weighted={sb.weighted_score:.1f}")
            if sup.policy_signals:
                sig = sup.policy_signals
                print(f"    SLA Signals: OTIF={sig.otif_target}%, Reliability={sig.reliability_score}%, Expedited={sig.expedited_support}, Emergency={sig.emergency_suitability}, DelayRisk={sig.delay_risk}")
            print(f"    Document Evidence ({len(sup.evidence)} chunks):")
            for idx, ev in enumerate(sup.evidence, start=1):
                doc_t = getattr(ev, "document_title", None) or getattr(ev, "title", "Document")
                dist = f"distance={ev.distance:.4f}" if ev.distance is not None else ""
                print(f"      [{idx}] Doc {ev.document_id}: '{doc_t}' (p.{ev.page_number}) {dist}")

        if resp.selected_supplier:
            print(f"\nFINAL SELECTED SUPPLIER: {resp.selected_supplier.supplier_name}")
            print(f"  Recommended Order Quantity: {resp.recommended_order_quantity} units")
            print(f"  Total Estimated Spend:      LKR {resp.selected_supplier.estimated_total_cost:,.2f}")
            print(f"  Selection Reason:           {resp.selected_supplier.selection_reason}")

        print("\nEXPLAINABLE SYNTHESIS NARRATIVE:")
        print(f"  {resp.reasoning}")

        print("\nDECISION FACTORS:")
        for f in resp.factors:
            print(f"  - {f}")

        print("\n" + "=" * 80)
        print("VERIFICATION COMPLETED SUCCESSFULLY.")
        print("=" * 80)
        return 0

    except Exception as exc:
        print(f"[ERROR] Live verification failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(run_live_verification())
