"""
Comprehensive Test Suite for SmartSupply Decision Intelligence Upgrade:
- Automatic urgency derivation (Normal, High, Emergency)
- Timing calculations (days_until_unsafe, days_until_stockout, required_delivery_window_days)
- Delivery slack calculation and feasibility gating (lead_time > window -> disqualified)
- Situation-aware supplier candidate scoring (Normal, High, Emergency weight matrices)
- Zero-slack penalty under High urgency
- Manual urgency override and audit tracking
- Document IR policy weights and grounded SLA signals extraction
- PostgreSQL authority enforcement (documents cannot alter commercial terms)
- Replenishment pipeline preservation (ROP safety buffer, incoming pipeline, MOQ)
- Scenarios A through F deterministic validation
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.supplier import Supplier
from app.models.product_supplier import ProductSupplier
from app.schemas.decision import (
    DecisionRecommendationRequest,
    ScoreBreakdown,
    SupplierPolicySignals,
)
from app.services.decision_service import (
    derive_delivery_window_and_timing,
    derive_procurement_urgency,
    extract_supplier_policy_signals,
    extract_procurement_policy,
    score_supplier_candidate,
    select_best_supplier_candidate,
    calculate_replenishment_shortage,
)
from app.agents.decision.agent import DecisionAgent


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 1. TIMING & DELIVERY WINDOW TESTS
# ==============================================================================

def test_timing_zero_daily_demand():
    """When daily demand is 0, window should default to forecast horizon."""
    daily = [{"forecasted_quantity": 0.0}] * 14
    result = derive_delivery_window_and_timing(
        available_stock=50, incoming_stock=0, reorder_point=30,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert result["days_until_unsafe"] is None
    assert result["days_until_stockout"] is None
    assert result["required_delivery_window_days"] == 14


def test_timing_immediate_unsafe():
    """When effective inventory is already below ROP, days_until_unsafe is 0."""
    daily = [{"forecasted_quantity": 10.0}] * 14
    result = derive_delivery_window_and_timing(
        available_stock=20, incoming_stock=0, reorder_point=30,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert result["days_until_unsafe"] == 0
    # Day 1: 20 - 10 = 10, Day 2: 10 - 10 = 0 <= 0 (stockout on day 2)
    assert result["days_until_stockout"] == 2
    # Stockout on day 2 governs delivery feasibility
    assert result["required_delivery_window_days"] == 2


def test_timing_future_unsafe_and_stockout():
    """Correctly simulates daily inventory depletion trajectory using available stock."""
    # Available = 40, Incoming = 40, ROP = 30, daily demand = 10
    # Available stock trajectory: Day 1: 30 <= 30 -> buffer breach day 1; Day 4: 0 <= 0 -> stockout day 4
    daily = [{"forecasted_quantity": 10.0}] * 14
    result = derive_delivery_window_and_timing(
        available_stock=40, incoming_stock=40, reorder_point=30,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert result["days_until_unsafe"] == 1
    assert result["days_until_stockout"] == 4
    assert result["required_delivery_window_days"] == 1


def test_timing_available_below_rop_breached_now():
    """1. available=18, ROP=20 -> buffer breach = 0, stockout and delivery window preserved."""
    daily = [{"forecasted_quantity": 9.0}] * 14
    result = derive_delivery_window_and_timing(
        available_stock=18, incoming_stock=40, reorder_point=20,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert result["days_until_buffer_breach"] == 0
    assert result["days_until_unsafe"] == 0
    # Day 1: 18 - 9 = 9, Day 2: 9 - 9 = 0 (stockout on day 2)
    assert result["days_until_stockout"] == 2
    # Buffer breach = 0 does NOT force required window to 0; stockout at 2 governs window
    assert result["required_delivery_window_days"] == 2


def test_timing_incoming_does_not_delay_buffer_breach():
    """2. incoming=40 does not delay buffer timing because ETA is unknown."""
    daily = [{"forecasted_quantity": 10.0}] * 14
    res_no_incoming = derive_delivery_window_and_timing(
        available_stock=50, incoming_stock=0, reorder_point=30,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    res_with_incoming = derive_delivery_window_and_timing(
        available_stock=50, incoming_stock=40, reorder_point=30,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert res_no_incoming["days_until_buffer_breach"] == 2
    assert res_with_incoming["days_until_buffer_breach"] == 2


def test_timing_buffer_breach_never_after_stockout():
    """3. Invariant: buffer breach never occurs after stockout (days_until_buffer_breach <= days_until_stockout)."""
    daily = [{"forecasted_quantity": 15.0}] * 14
    res = derive_delivery_window_and_timing(
        available_stock=20, incoming_stock=100, reorder_point=0,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert res["days_until_buffer_breach"] is not None
    assert res["days_until_stockout"] is not None
    assert res["days_until_buffer_breach"] <= res["days_until_stockout"]


def test_digital_sla_evidence_suppresses_missing_doc_warning():
    """4. Digital Distribution has SLA evidence -> no missing-SLA warning."""
    from app.services.chat_presentation import build_decision_reason_bullets
    rec = {
        "replenishment_required": True,
        "recommended_order_quantity": 131,
        "selected_supplier": {
            "supplier_id": 10,
            "supplier_name": "Digital Distribution Lanka",
            "lead_time_days": 3,
            "delivery_slack_days": 0,
            "evidence": [
                {"document_id": 1, "document_title": "Digital Distribution SLA", "text": "OTIF 98%"}
            ],
        },
        "days_until_stockout": 2,
        "days_until_buffer_breach": 0,
        "warnings": [
            "Supplier 10 lacks any performance or SLA documentation, creating uncertainty around delivery reliability and emergency handling."
        ],
    }
    bullets = build_decision_reason_bullets(rec)
    for b in bullets:
        assert "lacks any performance or sla documentation" not in b.lower()
        assert "supplier 10 lacks" not in b.lower()


# ==============================================================================
# 2. AUTOMATIC URGENCY DERIVATION TESTS
# ==============================================================================

def test_urgency_emergency_stockout_within_2_days():
    """Stockout within 2 days must trigger Emergency urgency."""
    urgency, reason = derive_procurement_urgency(
        replenishment_required=True,
        stockout_risk_level="HIGH",
        days_until_unsafe=1,
        days_until_stockout=2,
        required_delivery_window_days=2,
        active_lead_times=[3, 5, 7],
        available_stock=20,
        reorder_point=30,
    )
    assert urgency == "emergency"
    assert "available-to-fulfil inventory exhaustion is projected" in reason.lower()


def test_urgency_emergency_window_below_fastest_lead_time():
    """When required window is less than or equal to fastest lead time, trigger Emergency."""
    urgency, reason = derive_procurement_urgency(
        replenishment_required=True,
        stockout_risk_level="MEDIUM",
        days_until_unsafe=2,
        days_until_stockout=4,
        required_delivery_window_days=2,
        active_lead_times=[3, 5, 7],
        available_stock=20,
        reorder_point=30,
    )
    assert urgency == "emergency"


def test_urgency_high_condition():
    """Unsafe within 5 days with window < max lead time triggers High urgency."""
    urgency, reason = derive_procurement_urgency(
        replenishment_required=True,
        stockout_risk_level="HIGH",
        days_until_unsafe=5,
        days_until_stockout=8,
        required_delivery_window_days=5,
        active_lead_times=[2, 5, 7],
        available_stock=30,
        reorder_point=20,
    )
    assert urgency == "high"
    assert "unsafe within approximately" in reason.lower()


def test_urgency_normal_condition():
    """Comfortable inventory buffer where window >= max lead time triggers Normal urgency."""
    urgency, reason = derive_procurement_urgency(
        replenishment_required=True,
        stockout_risk_level="LOW",
        days_until_unsafe=10,
        days_until_stockout=14,
        required_delivery_window_days=10,
        active_lead_times=[2, 5, 7],
        available_stock=100,
        reorder_point=40,
    )
    assert urgency == "normal"
    assert "sufficient delivery time exists" in reason.lower()


def test_urgency_no_replenishment():
    """When replenishment is not required, defaults to normal state."""
    urgency, reason = derive_procurement_urgency(
        replenishment_required=False,
        stockout_risk_level="LOW",
        days_until_unsafe=None,
        days_until_stockout=None,
        required_delivery_window_days=14,
        active_lead_times=[2, 5, 7],
        available_stock=200,
        reorder_point=30,
    )
    assert urgency == "normal"
    assert "no replenishment is currently required" in reason.lower()


# ==============================================================================
# 3. DELIVERY SLACK & FEASIBILITY GATING TESTS
# ==============================================================================

def test_delivery_slack_and_feasibility():
    """Delivery slack is required_window - lead_time. Disqualified if slack < 0."""
    candidate_fast = {"supplier_id": 1, "supplier_name": "Fast", "unit_cost": 100.0, "lead_time_days": 3, "moq": 1}
    candidate_slow = {"supplier_id": 2, "supplier_name": "Slow", "unit_cost": 80.0, "lead_time_days": 7, "moq": 1}
    all_cands = [candidate_fast, candidate_slow]
    window = 5
    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}
    signals = SupplierPolicySignals(compliance_status="eligible")

    # Fast: 5 - 3 = +2 slack (feasible)
    brk_fast, status_fast, reason_fast, slack_fast = score_supplier_candidate(
        candidate=candidate_fast, required_delivery_window_days=window, urgency="normal",
        weights=weights, policy_signals=signals, all_candidates=all_cands
    )
    assert slack_fast == 2
    assert status_fast == "eligible"

    # Slow: 5 - 7 = -2 slack (infeasible)
    brk_slow, status_slow, reason_slow, slack_slow = score_supplier_candidate(
        candidate=candidate_slow, required_delivery_window_days=window, urgency="normal",
        weights=weights, policy_signals=signals, all_candidates=all_cands
    )
    assert slack_slow == -2
    assert status_slow == "infeasible"
    assert "exceeds" in reason_slow.lower()


def test_zero_slack_penalty_in_high_urgency():
    """Zero slack in High urgency receives a penalty in delivery score."""
    candidate_tight = {"supplier_id": 1, "supplier_name": "TightVendor", "unit_cost": 50.0, "lead_time_days": 5, "moq": 1}
    candidate_margin = {"supplier_id": 2, "supplier_name": "MarginVendor", "unit_cost": 50.0, "lead_time_days": 2, "moq": 1}
    all_cands = [candidate_tight, candidate_margin]
    window = 5  # tight has slack 0, margin has slack 3
    weights = {"cost": 0.40, "delivery": 0.40, "sla": 0.20}
    signals = SupplierPolicySignals(compliance_status="eligible")

    brk_tight, status_tight, _, slack_tight = score_supplier_candidate(
        candidate_tight, window, "high", weights, signals, all_cands
    )
    brk_margin, status_margin, _, slack_margin = score_supplier_candidate(
        candidate_margin, window, "high", weights, signals, all_cands
    )

    assert slack_tight == 0
    assert slack_margin == 3
    # Margin vendor should have higher delivery score than tight vendor
    assert brk_margin.delivery_score > brk_tight.delivery_score
    assert brk_margin.weighted_score > brk_tight.weighted_score


# ==============================================================================
# 4. SITUATION-AWARE SCORING MATRIX TESTS
# ==============================================================================

def test_extract_procurement_policy_weights():
    """Verifies approved SmartSupply weight matrix across urgency tiers."""
    weights, warnings = extract_procurement_policy([])
    assert weights["normal"] == {"cost": 0.60, "delivery": 0.20, "sla": 0.20}
    assert weights["high"] == {"cost": 0.40, "delivery": 0.40, "sla": 0.20}
    assert weights["emergency"] == {"cost": 0.15, "delivery": 0.60, "sla": 0.25}


def test_restricted_supplier_is_disqualified():
    """A supplier marked restricted in policy signals must be disqualified."""
    signals = SupplierPolicySignals(compliance_status="restricted")
    cand = {"supplier_id": 10, "supplier_name": "BadVendor", "unit_cost": 10.0, "lead_time_days": 1, "moq": 1, "policy_signals": signals}
    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}

    brk, status, reason, _ = score_supplier_candidate(
        cand, 10, "normal", weights, signals, [cand]
    )
    assert status == "policy_restricted"
    assert "restricted" in reason.lower()

    best, _, warnings, _, enriched = select_best_supplier_candidate(
        candidates=[cand], recommended_quantity=10, urgency="normal", required_delivery_window_days=10, return_enriched=True
    )
    assert best is None
    assert any("restriction" in w.lower() or "disqualified" in w.lower() for w in warnings)


# ==============================================================================
# 5. DOCUMENT IR SIGNALS & GROUNDING TESTS
# ==============================================================================

def test_extract_supplier_policy_signals_grounding():
    """Extracts OTIF, expedited capabilities, and restrictions from grounded text chunks."""
    evidence = [
        {"document_id": 25, "text": "Contracted minimum OTIF delivery commitment is 95.0%. Supplier offers expedited orders with rapid dispatch."},
        {"document_id": 26, "text": "Overall performance review overall score 92.5 out of 100 with reliable benchmark standard."},
    ]
    cand = {"supplier_id": 1, "supplier_name": "TestVendor", "evidence": evidence}
    signals = extract_supplier_policy_signals(cand, evidence)

    assert signals.compliance_status == "eligible"
    assert signals.otif_target == 95.0
    assert signals.expedited_support == "strong"
    assert signals.delay_risk == "low"
    assert 25 in signals.evidence_refs
    assert 26 in signals.evidence_refs


def test_postgresql_authority_over_documents():
    """
    PostgreSQL DB unit_cost and lead_time are authoritative.
    Even if document claims lower cost, scoring uses candidate dictionary from DB.
    """
    fake_doc = [{"document_id": 1, "text": "Special discount: unit price LKR 10.00, lead time 1 day guaranteed."}]
    signals = extract_supplier_policy_signals({"evidence": fake_doc})

    # PostgreSQL candidate has unit_cost = 550.0, lead_time = 5
    cand_db = {"supplier_id": 2, "supplier_name": "HonestDBVendor", "unit_cost": 550.0, "lead_time_days": 5, "moq": 1}
    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}

    brk, status, reason, slack = score_supplier_candidate(cand_db, 10, "normal", weights, signals, [cand_db])
    # The slack must be 10 - 5 = 5 (using DB lead time 5, NOT document's 1 day!)
    assert slack == 5


# ==============================================================================
# 6. CONTROLLED SCENARIOS A THROUGH F (PART 25)
# ==============================================================================

def test_scenario_a_normal_replenishment():
    """
    Scenario A: Stock comfortable, window is 14 days.
    Lowest cost supplier (NextGen @ LKR 480) wins under Normal urgency (60% cost).
    """
    candidates = [
        {"supplier_id": 1, "supplier_name": "NextGen", "unit_cost": 480.0, "lead_time_days": 7, "moq": 10},
        {"supplier_id": 2, "supplier_name": "TechSource", "unit_cost": 550.0, "lead_time_days": 5, "moq": 5},
        {"supplier_id": 3, "supplier_name": "DigitalDist", "unit_cost": 620.0, "lead_time_days": 2, "moq": 1},
    ]
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates, recommended_quantity=60, urgency="normal", required_delivery_window_days=14, return_enriched=True
    )
    assert best["supplier_id"] == 1
    assert best["supplier_name"] == "NextGen"


def test_scenario_b_high_urgency_tight_window():
    """
    Scenario B: Days until unsafe = 5. Window = 5.
    - NextGen (LT=7) is infeasible (slack = -2).
    - TechSource (LT=5) is tight (slack = 0).
    - DigitalDist (LT=2) has delivery margin (slack = +3).
    Under High urgency (40% delivery, 40% cost, 20% SLA), DigitalDist wins.
    """
    candidates = [
        {"supplier_id": 1, "supplier_name": "NextGen", "unit_cost": 480.0, "lead_time_days": 7, "moq": 10},
        {"supplier_id": 2, "supplier_name": "TechSource", "unit_cost": 550.0, "lead_time_days": 5, "moq": 5},
        {"supplier_id": 3, "supplier_name": "DigitalDist", "unit_cost": 620.0, "lead_time_days": 2, "moq": 1},
    ]
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates, recommended_quantity=60, urgency="high", required_delivery_window_days=5, return_enriched=True
    )
    next_gen = next(c for c in enriched if c["supplier_id"] == 1)
    assert next_gen["is_feasible"] is False
    assert next_gen["delivery_slack_days"] == -2

    assert best["supplier_id"] == 3
    assert best["supplier_name"] == "DigitalDist"
    assert best["delivery_slack_days"] == 3


def test_scenario_c_emergency_stockout():
    """
    Scenario C: Window is 2 days. Fastest supplier wins under Emergency urgency.
    """
    candidates = [
        {"supplier_id": 1, "supplier_name": "NextGen", "unit_cost": 480.0, "lead_time_days": 7, "moq": 10},
        {"supplier_id": 2, "supplier_name": "TechSource", "unit_cost": 550.0, "lead_time_days": 5, "moq": 5},
        {"supplier_id": 3, "supplier_name": "DigitalDist", "unit_cost": 620.0, "lead_time_days": 2, "moq": 1},
    ]
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates, recommended_quantity=50, urgency="emergency", required_delivery_window_days=2, return_enriched=True
    )
    assert best["supplier_id"] == 3
    assert best["supplier_name"] == "DigitalDist"


def test_scenario_d_manual_override_auditing(db_session: Session):
    """
    Scenario D: System derives Normal, but user provides manual override to Emergency.
    Decision agent must apply Emergency scoring weights and audit the override.
    """
    product = Product(name="Item A", sku="SKU-A", reorder_point=20, is_active=True)
    db_session.add(product)
    db_session.flush()

    inventory = Inventory(product_id=product.id, on_hand=100, reserved=0, incoming=0)
    db_session.add(inventory)

    sup1 = Supplier(supplier_code="SUP-001", name="SlowCheap", is_active=True)
    sup2 = Supplier(supplier_code="SUP-002", name="FastCostly", is_active=True)
    db_session.add_all([sup1, sup2])
    db_session.flush()

    ps1 = ProductSupplier(product_id=product.id, supplier_id=sup1.id, unit_cost=Decimal("100.00"), moq=1, lead_time_days=8, is_active=True)
    ps2 = ProductSupplier(product_id=product.id, supplier_id=sup2.id, unit_cost=Decimal("200.00"), moq=1, lead_time_days=2, is_active=True)
    db_session.add_all([ps1, ps2])
    db_session.commit()

    agent = DecisionAgent()
    req = DecisionRecommendationRequest(
        product_id=product.id,
        forecast_horizon_days=14,
        urgency_override="emergency"
    )

    with patch("app.agents.decision.agent.analyze_product_demand_from_db") as mock_demand, \
         patch("app.agents.decision.agent.SupplierProcurementAgent.assess_suppliers") as mock_sup:
        
        mock_demand.return_value = {
            "total_forecasted_demand": 140.0,
            "stockout_risk": {
                "expected_demand_over_lead_time": 20.0,
                "risk_level": "LOW",
                "projected_stockout_date": None,
            },
            "evaluation_metrics": {"selected_model": "HoltWinters"},
            "daily_forecasts": [{"forecasted_quantity": 10.0}] * 14,
        }
        mock_sup.return_value = MagicMock(
            advisory_supplier=None,
            policy_constraints=[],
            warnings=[],
            candidate_assessments=[
                MagicMock(
                    model_dump=lambda: {
                        "supplier_id": sup1.id,
                        "supplier_name": "SlowCheap",
                        "unit_cost": 100.0,
                        "moq": 1,
                        "lead_time_days": 8,
                        "advantages": [],
                        "risks": [],
                        "evidence": [],
                    },
                    evidence=[]
                ),
                MagicMock(
                    model_dump=lambda: {
                        "supplier_id": sup2.id,
                        "supplier_name": "FastCostly",
                        "unit_cost": 200.0,
                        "moq": 1,
                        "lead_time_days": 2,
                        "advantages": [],
                        "risks": [],
                        "evidence": [],
                    },
                    evidence=[]
                ),
            ]
        )

        resp = agent.generate_recommendation(db=db_session, request=req)

        assert resp.effective_urgency == "emergency"
        assert resp.manual_override_applied is True
        assert resp.manual_urgency_override == "emergency"
        assert any("was manually selected" in w for w in resp.warnings)


def test_scenario_e_disqualification_due_to_lead_time():
    """
    Scenario E: When lead time > required window, candidate must be marked infeasible
    and cannot be selected even if unit cost is cheap.
    """
    candidates = [
        {"supplier_id": 1, "supplier_name": "ZeroCostLate", "unit_cost": 0.01, "lead_time_days": 10, "moq": 1},
        {"supplier_id": 2, "supplier_name": "FeasibleVendor", "unit_cost": 500.0, "lead_time_days": 4, "moq": 1},
    ]
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates, recommended_quantity=100, urgency="high", required_delivery_window_days=4, return_enriched=True
    )
    assert best["supplier_id"] == 2
    assert best["supplier_name"] == "FeasibleVendor"
    assert enriched[0]["is_feasible"] is False


def test_scenario_f_sla_performance_tie_breaker():
    """
    Scenario F: When cost and lead times are identical, higher SLA OTIF & reliability wins.
    """
    cand_low_sla = {
        "supplier_id": 1, "supplier_name": "LowSLA", "unit_cost": 500.0, "lead_time_days": 5, "moq": 1,
        "evidence": [{"document_id": 10, "text": "Contracted minimum OTIF delivery commitment is 80.0% with elevated variance delay risk high."}]
    }
    cand_high_sla = {
        "supplier_id": 2, "supplier_name": "HighSLA", "unit_cost": 500.0, "lead_time_days": 5, "moq": 1,
        "evidence": [{"document_id": 11, "text": "Contracted minimum OTIF delivery commitment is 98.0% with priority dispatch and benchmark standard."}]
    }
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=[cand_low_sla, cand_high_sla], recommended_quantity=50, urgency="normal", required_delivery_window_days=10, return_enriched=True
    )
    assert best["supplier_id"] == 2
    assert best["supplier_name"] == "HighSLA"


# ==============================================================================
# 7. PRESERVATION OF REPLENISHMENT BUSINESS LOGIC
# ==============================================================================

def test_replenishment_shortage_with_incoming_stock():
    """
    Preserves confirmed pipeline incoming stock in effective inventory:
    shortage = max(0, (forecasted_demand + ROP) - (available + incoming))
    """
    # available = 24, incoming = 60 (effective = 84), ROP = 30, demand = 184
    # target = 184 + 30 = 214. Effective = 84. Shortage = 214 - 84 = 130
    req, raw_qty, metrics = calculate_replenishment_shortage(
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0,
        incoming_stock=60
    )
    assert req is True
    assert raw_qty == 130
    assert metrics["effective_inventory"] == 84


def test_replenishment_shortage_zero_when_stock_adequate():
    """No replenishment when effective inventory satisfies demand + ROP."""
    req, raw_qty, metrics = calculate_replenishment_shortage(
        available_stock=200,
        reorder_point=30,
        predicted_demand=100.0,
        incoming_stock=50
    )
    assert req is False
    assert raw_qty == 0


# ==============================================================================
# 8. ADDITIONAL DECISION INTELLIGENCE EDGE CASES
# ==============================================================================

def test_override_auto_defaults_to_derived(db_session: Session):
    """When urgency_override='auto', derived urgency is preserved without override warning."""
    product = Product(name="Item Auto", sku="SKU-AUTO", reorder_point=20, is_active=True)
    db_session.add(product)
    db_session.flush()

    inventory = Inventory(product_id=product.id, on_hand=100, reserved=0, incoming=0)
    db_session.add(inventory)

    sup1 = Supplier(supplier_code="SUP-AUTO", name="AutoSup", is_active=True)
    db_session.add(sup1)
    db_session.flush()

    ps1 = ProductSupplier(product_id=product.id, supplier_id=sup1.id, unit_cost=Decimal("100.00"), moq=1, lead_time_days=3, is_active=True)
    db_session.add(ps1)
    db_session.commit()

    agent = DecisionAgent()
    req = DecisionRecommendationRequest(
        product_id=product.id,
        forecast_horizon_days=14,
        urgency_override="auto"
    )

    with patch("app.agents.decision.agent.analyze_product_demand_from_db") as mock_demand, \
         patch("app.agents.decision.agent.SupplierProcurementAgent.assess_suppliers") as mock_sup:
        
        mock_demand.return_value = {
            "total_forecasted_demand": 50.0,
            "stockout_risk": {"expected_demand_over_lead_time": 10.0, "risk_level": "LOW", "projected_stockout_date": None},
            "evaluation_metrics": {"selected_model": "HoltWinters"},
            "daily_forecasts": [{"forecasted_quantity": 3.0}] * 14,
        }
        mock_sup.return_value = MagicMock(
            advisory_supplier=None, policy_constraints=[], warnings=[],
            candidate_assessments=[MagicMock(model_dump=lambda: {"supplier_id": sup1.id, "supplier_name": "AutoSup", "unit_cost": 100.0, "moq": 1, "lead_time_days": 3}, evidence=[])]
        )

        resp = agent.generate_recommendation(db=db_session, request=req)
        assert resp.manual_override_applied is False
        assert resp.manual_urgency_override is None
        assert not any("was manually selected" in w for w in resp.warnings)


def test_override_same_as_derived_generates_no_discrepancy_warning(db_session: Session):
    """When user manually selects an urgency that matches derived urgency, no audit warning is produced."""
    product = Product(name="Item Match", sku="SKU-MATCH", reorder_point=20, is_active=True)
    db_session.add(product)
    db_session.flush()

    inventory = Inventory(product_id=product.id, on_hand=100, reserved=0, incoming=0)
    db_session.add(inventory)

    sup1 = Supplier(supplier_code="SUP-M", name="MatchSup", is_active=True)
    db_session.add(sup1)
    db_session.flush()

    ps1 = ProductSupplier(product_id=product.id, supplier_id=sup1.id, unit_cost=Decimal("100.00"), moq=1, lead_time_days=3, is_active=True)
    db_session.add(ps1)
    db_session.commit()

    agent = DecisionAgent()
    # If derived urgency is normal, user sends normal
    req = DecisionRecommendationRequest(
        product_id=product.id,
        forecast_horizon_days=14,
        urgency_override="normal"
    )

    with patch("app.agents.decision.agent.analyze_product_demand_from_db") as mock_demand, \
         patch("app.agents.decision.agent.SupplierProcurementAgent.assess_suppliers") as mock_sup:
        
        mock_demand.return_value = {
            "total_forecasted_demand": 50.0,
            "stockout_risk": {"expected_demand_over_lead_time": 10.0, "risk_level": "LOW", "projected_stockout_date": None},
            "evaluation_metrics": {"selected_model": "HoltWinters"},
            "daily_forecasts": [{"forecasted_quantity": 3.0}] * 14,
        }
        mock_sup.return_value = MagicMock(
            advisory_supplier=None, policy_constraints=[], warnings=[],
            candidate_assessments=[MagicMock(model_dump=lambda: {"supplier_id": sup1.id, "supplier_name": "MatchSup", "unit_cost": 100.0, "moq": 1, "lead_time_days": 3}, evidence=[])]
        )

        resp = agent.generate_recommendation(db=db_session, request=req)
        assert resp.effective_urgency == "normal"
        assert resp.manual_override_applied is False
        assert not any("was manually selected" in w for w in resp.warnings)


def test_zero_slack_penalty_not_applied_in_normal_urgency():
    """Zero slack does not receive -0.10 deduction in Normal urgency (cost prioritized)."""
    cand = {"supplier_id": 1, "supplier_name": "Vendor", "unit_cost": 100.0, "lead_time_days": 5, "moq": 1}
    signals = SupplierPolicySignals(compliance_status="eligible")
    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}

    brk, status, _, slack = score_supplier_candidate(
        cand, required_delivery_window_days=5, urgency="normal", weights=weights, policy_signals=signals, all_candidates=[cand]
    )
    assert slack == 0
    assert status == "zero_slack"


def test_single_candidate_infeasible_triggers_exception_protocol():
    """When no supplier meets delivery window, exception protocol selects fastest compliant supplier with warning."""
    candidates = [
        {"supplier_id": 1, "supplier_name": "OnlyLateSupplier", "unit_cost": 300.0, "lead_time_days": 10, "moq": 1}
    ]
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates, recommended_quantity=50, urgency="emergency", required_delivery_window_days=3, return_enriched=True
    )
    assert best["supplier_id"] == 1
    assert any("No available supplier can fully meet" in w for w in warnings)


def test_moq_clamping_on_selected_supplier():
    """If recommended quantity is less than supplier MOQ, final quantity clamps to MOQ."""
    candidates = [
        {"supplier_id": 1, "supplier_name": "BulkSupplier", "unit_cost": 200.0, "lead_time_days": 5, "moq": 100}
    ]
    best, final_qty, _, _, _ = select_best_supplier_candidate(
        candidates=candidates, recommended_quantity=45, urgency="normal", required_delivery_window_days=10, return_enriched=True
    )
    assert best["supplier_id"] == 1
    assert final_qty == 100


def test_extreme_cost_spread_normalization():
    """Handles extreme cost differences without numerical instability."""
    cand_cheap = {"supplier_id": 1, "supplier_name": "UltraCheap", "unit_cost": 10.0, "lead_time_days": 5, "moq": 1}
    cand_expensive = {"supplier_id": 2, "supplier_name": "UltraExpensive", "unit_cost": 10000.0, "lead_time_days": 5, "moq": 1}
    all_cands = [cand_cheap, cand_expensive]
    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}
    signals = SupplierPolicySignals(compliance_status="eligible")

    brk_cheap, _, _, _ = score_supplier_candidate(cand_cheap, 10, "normal", weights, signals, all_cands)
    brk_exp, _, _, _ = score_supplier_candidate(cand_expensive, 10, "normal", weights, signals, all_cands)

    assert brk_cheap.cost_score == 100.0
    assert brk_exp.cost_score <= 1.0
    assert brk_cheap.weighted_score > brk_exp.weighted_score


def test_days_until_stockout_is_none_when_demand_low():
    """Physical stock never exhausts when demand is less than available stock."""
    daily = [{"forecasted_quantity": 2.0}] * 14
    result = derive_delivery_window_and_timing(
        available_stock=100, incoming_stock=0, reorder_point=20,
        daily_forecasts=daily, forecast_horizon_days=14
    )
    assert result["days_until_stockout"] is None


def test_evidence_refs_collection_in_supplier_signals():
    """Grounded evidence document IDs are accurately tracked in SupplierPolicySignals."""
    evidence = [
        {"document_id": 25, "text": "Terms and conditions."},
        {"document_id": 25, "text": "Duplicate document chunk."},
        {"document_id": 30, "text": "Performance review."},
    ]
    signals = extract_supplier_policy_signals({"evidence": evidence})
    assert sorted(signals.evidence_refs) == [25, 30]


# ==============================================================================
# 9. SECTION 17: DETERMINISTIC TIMING & INCOMING STOCK TESTS
# ==============================================================================

def test_timing_buffer_breach_5d_stockout_2d_window_2d():
    """
    Test 17.1: Buffer breach (Day 0 since available 24 <= ROP 30) + stockout 2d -> required delivery window = 2d.
    When available <= ROP, buffer is breached NOW (0), and stockout governs required delivery window.
    """
    daily_demo = [{"forecasted_quantity": 12.0}] * 7
    result = derive_delivery_window_and_timing(
        available_stock=24,
        reorder_point=30,
        daily_forecasts=daily_demo,
        forecast_horizon_days=14,
        incoming_stock=60,
    )
    assert result["days_until_buffer_breach"] == 0
    assert result["days_until_stockout"] == 2
    assert result["required_delivery_window_days"] == 2


def test_timing_buffer_breach_5d_no_physical_stockout():
    """
    Test 17.2: Buffer breach 5d + no physical stockout in horizon -> required delivery window = 5d.
    """
    # Available = 100, Incoming = 0, ROP = 50.
    # Daily demand = 10.
    # Day 1: 90, Day 2: 80, Day 3: 70, Day 4: 60, Day 5: 50 (at ROP), Day 6: 40 < 50 (breach Day 6 or Day 5)
    # Let's craft demand so breach is at Day 5: Day 1..4: 10 (rem 60), Day 5: 11 (rem 49 < 50 -> breach Day 5)
    # Physical stock remaining at Day 5: 49 > 0 (no stockout in 7-day horizon if next days are small)
    daily = [
        {"forecasted_quantity": 10.0},
        {"forecasted_quantity": 10.0},
        {"forecasted_quantity": 10.0},
        {"forecasted_quantity": 10.0},
        {"forecasted_quantity": 11.0},
        {"forecasted_quantity": 1.0},
        {"forecasted_quantity": 1.0},
    ]
    result = derive_delivery_window_and_timing(
        available_stock=100,
        reorder_point=50,
        daily_forecasts=daily,
        forecast_horizon_days=7,
        incoming_stock=0,
    )
    assert result["days_until_buffer_breach"] == 5
    assert result["days_until_stockout"] is None
    assert result["required_delivery_window_days"] == 5


def test_timing_no_buffer_breach_no_stockout_fallback():
    """
    Test 17.3: No buffer breach + no stockout -> normal/fallback behavior (horizon days).
    """
    daily = [{"forecasted_quantity": 2.0}] * 14
    result = derive_delivery_window_and_timing(
        available_stock=100,
        reorder_point=20,
        daily_forecasts=daily,
        forecast_horizon_days=14,
        incoming_stock=0,
    )
    assert result["days_until_buffer_breach"] is None
    assert result["days_until_stockout"] is None
    assert result["required_delivery_window_days"] == 14


def test_timing_unknown_incoming_eta_cannot_create_recovery_day():
    """
    Test 17.4 & 17.6: Unknown incoming ETA cannot create a recovery day or fake timing event.
    Timing trajectory must NOT inject incoming stock on a specific forecast day.
    """
    # Available = 10, Incoming = 100, ROP = 20. Daily demand = 5.
    # Physical trajectory without ETA: Day 1: 5, Day 2: 0 (stockout Day 2).
    # Incoming stock (100) must NOT artificially replenish physical stock on Day 3.
    daily = [{"forecasted_quantity": 5.0}] * 7
    result = derive_delivery_window_and_timing(
        available_stock=10,
        reorder_point=20,
        daily_forecasts=daily,
        forecast_horizon_days=7,
        incoming_stock=100,
    )
    # Physical stockout occurs on Day 2 regardless of incoming quantity because arrival timing is unknown
    assert result["days_until_stockout"] == 2
    assert result["required_delivery_window_days"] == 2


def test_incoming_quantity_reduces_replenishment_quantity_without_fake_timing():
    """
    Test 17.5: Confirmed incoming quantity still reduces replenishment shortage quantity,
    demonstrating clear separation: quantity planning uses incoming, timing does not inject fake ETA.
    """
    # Demand = 100, ROP = 30 -> Target = 130
    # Available = 20, Incoming = 50 -> Effective = 70
    # Net requirement = 130 - 70 = 60
    req, qty, metrics = calculate_replenishment_shortage(
        available_stock=20,
        reorder_point=30,
        predicted_demand=100.0,
        incoming_stock=50,
    )
    assert req is True
    assert qty == 60
    assert metrics["effective_inventory"] == 70

    # Without incoming stock (incoming = 0): Net requirement = 130 - 20 = 110
    req_no_inc, qty_no_inc, _ = calculate_replenishment_shortage(
        available_stock=20,
        reorder_point=30,
        predicted_demand=100.0,
        incoming_stock=0,
    )
    assert qty_no_inc == 110
    # Exactly 50 units less replenishment needed
    assert qty_no_inc - qty == 50


# ==============================================================================
# 10. SECTION 18: DETERMINISTIC FEASIBILITY GATING TESTS
# ==============================================================================

def test_feasibility_with_required_window_2d():
    """
    Test 18: Using required window 2d:
    - NextGen (7d): slack = 2 - 7 = -5 -> infeasible
    - TechSource (5d): slack = 2 - 5 = -3 -> infeasible
    - Digital (2d): slack = 2 - 2 = 0 -> feasible, zero margin
    """
    candidates = [
        {"supplier_id": 11, "supplier_name": "NextGen Supplies", "unit_cost": 480.0, "lead_time_days": 7, "moq": 10},
        {"supplier_id": 9, "supplier_name": "TechSource Lanka", "unit_cost": 550.0, "lead_time_days": 5, "moq": 5},
        {"supplier_id": 10, "supplier_name": "Digital Distribution", "unit_cost": 620.0, "lead_time_days": 2, "moq": 1},
    ]
    window = 2
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=50,
        urgency="emergency",
        required_delivery_window_days=window,
        return_enriched=True,
    )

    next_gen = next(c for c in enriched if c["supplier_id"] == 11)
    tech_source = next(c for c in enriched if c["supplier_id"] == 9)
    digital = next(c for c in enriched if c["supplier_id"] == 10)

    assert next_gen["delivery_slack_days"] == -5
    assert next_gen["is_feasible"] is False

    assert tech_source["delivery_slack_days"] == -3
    assert tech_source["is_feasible"] is False

    assert digital["delivery_slack_days"] == 0
    assert digital["is_feasible"] is True

    # Digital is the only feasible supplier and must win
    assert best["supplier_id"] == 10
    assert best["supplier_name"] == "Digital Distribution"


# ==============================================================================
# 11. SECTION 19: DETERMINISTIC SLA DIFFERENTIATION TESTS
# ==============================================================================

def test_sla_differentiation_between_suppliers():
    """
    Test 19.1: Supplier A (92% OTIF, limited emergency) receives a lower SLA score
    than Supplier B (98% OTIF, strong emergency) under EMERGENCY urgency.
    """
    cand_a = {
        "supplier_id": 1,
        "supplier_name": "Supplier A",
        "unit_cost": 500.0,
        "lead_time_days": 2,
        "moq": 1,
        "evidence": [
            {"document_id": 101, "text": "Contracted minimum OTIF delivery commitment is 92.0%. Supplier has limited expedited and emergency support with elevated delay risk high."}
        ]
    }
    cand_b = {
        "supplier_id": 2,
        "supplier_name": "Supplier B",
        "unit_cost": 500.0,
        "lead_time_days": 2,
        "moq": 1,
        "evidence": [
            {"document_id": 102, "text": "Contracted minimum OTIF delivery commitment is 98.4%. Supplier guarantees expedited orders, emergency dispatch preferred, delay risk low."}
        ]
    }
    all_cands = [cand_a, cand_b]
    weights = {"cost": 0.15, "delivery": 0.60, "sla": 0.25}

    sig_a = extract_supplier_policy_signals(cand_a, cand_a["evidence"])
    sig_b = extract_supplier_policy_signals(cand_b, cand_b["evidence"])

    brk_a, _, _, _ = score_supplier_candidate(cand_a, 2, "emergency", weights, sig_a, all_cands)
    brk_b, _, _, _ = score_supplier_candidate(cand_b, 2, "emergency", weights, sig_b, all_cands)

    assert sig_a.otif_target == 92.0
    assert sig_b.otif_target == 98.4
    assert brk_a.sla_score < brk_b.sla_score
    # Difference must be significant (>= 15 points)
    assert (brk_b.sla_score - brk_a.sla_score) >= 15.0


def test_sla_neutral_score_when_no_evidence():
    """
    Test 19.2 & 19.3: No evidence -> neutral score (80.0) with warning that SLA evidence was insufficient.
    Missing SLA evidence does not fabricate an OTIF value.
    """
    cand = {"supplier_id": 99, "supplier_name": "GhostVendor", "unit_cost": 500.0, "lead_time_days": 3, "moq": 1}
    signals = extract_supplier_policy_signals(cand, [])

    assert signals.otif_target is None
    assert signals.reliability_score is None

    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}
    brk, status, reason, slack = score_supplier_candidate(cand, 5, "normal", weights, signals, [cand])
    assert brk.sla_score == 80.0

    # select_best_supplier_candidate produces warning for insufficient SLA evidence
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=[cand], recommended_quantity=10, urgency="normal", return_enriched=True
    )
    assert enriched[0]["sla_score"] == 80.0
    assert any("insufficient" in w.lower() or "neutral" in w.lower() for w in warnings)


def test_retrieval_evidence_maps_to_actual_supplier():
    """
    Test 19.4: Evidence chunks map strictly to their respective supplier candidates.
    """
    evidence_nextgen = [{"document_id": 29, "text": "NextGen Supplies standard bulk order clause with 91.8% OTIF."}]
    evidence_digital = [{"document_id": 28, "text": "Digital Distribution rapid dispatch clause with 98.4% OTIF."}]

    cand_ng = {"supplier_id": 11, "supplier_name": "NextGen Supplies", "evidence": evidence_nextgen}
    cand_dd = {"supplier_id": 10, "supplier_name": "Digital Distribution", "evidence": evidence_digital}

    sig_ng = extract_supplier_policy_signals(cand_ng, evidence_nextgen)
    sig_dd = extract_supplier_policy_signals(cand_dd, evidence_digital)

    assert sig_ng.otif_target == 91.8
    assert sig_dd.otif_target == 98.4
    assert 29 in sig_ng.evidence_refs
    assert 28 in sig_dd.evidence_refs
    assert 29 not in sig_dd.evidence_refs


def test_supplier_name_alone_cannot_affect_sla_score():
    """
    Test 19.6: Supplier name alone cannot affect SLA score.
    A candidate named 'Digital Distribution' without evidence gets 80.0, identical to any other vendor without evidence.
    """
    cand_digital_no_ev = {"supplier_id": 10, "supplier_name": "Digital Distribution", "unit_cost": 500.0, "lead_time_days": 2, "moq": 1}
    cand_generic_no_ev = {"supplier_id": 999, "supplier_name": "Unknown Generic Supplier", "unit_cost": 500.0, "lead_time_days": 2, "moq": 1}

    sig_dd = extract_supplier_policy_signals(cand_digital_no_ev, [])
    sig_gen = extract_supplier_policy_signals(cand_generic_no_ev, [])

    weights = {"cost": 0.15, "delivery": 0.60, "sla": 0.25}
    brk_dd, _, _, _ = score_supplier_candidate(cand_digital_no_ev, 2, "emergency", weights, sig_dd, [cand_digital_no_ev, cand_generic_no_ev])
    brk_gen, _, _, _ = score_supplier_candidate(cand_generic_no_ev, 2, "emergency", weights, sig_gen, [cand_digital_no_ev, cand_generic_no_ev])

    assert brk_dd.sla_score == 80.0
    assert brk_gen.sla_score == 80.0
    assert brk_dd.sla_score == brk_gen.sla_score


# ==============================================================================
# 12. SECTION 20: IR MATERIAL IMPACT TEST
# ==============================================================================

def test_ir_material_impact_identical_pg_facts():
    """
    Test 20: Keep PostgreSQL facts identical between two synthetic candidates:
    same cost (500), MOQ (1), lead time (2).
    Change only grounded SLA evidence:
    - Supplier A: OTIF 92%, limited emergency
    - Supplier B: OTIF 98%, strong emergency
    Under EMERGENCY, Supplier B must score higher and be selected.
    This proves Document IR materially affects the procurement decision.
    """
    cand_a = {
        "supplier_id": 1,
        "supplier_name": "Candidate A",
        "unit_cost": 500.0,
        "lead_time_days": 2,
        "moq": 1,
        "evidence": [{"document_id": 201, "text": "Minimum OTIF commitment is 92.0% with limited emergency response."}]
    }
    cand_b = {
        "supplier_id": 2,
        "supplier_name": "Candidate B",
        "unit_cost": 500.0,
        "lead_time_days": 2,
        "moq": 1,
        "evidence": [{"document_id": 202, "text": "Minimum OTIF commitment is 98.0% with expedited orders and strong emergency support."}]
    }
    candidates = [cand_a, cand_b]
    best, final_qty, warnings, factors, enriched = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=50,
        urgency="emergency",
        required_delivery_window_days=2,
        return_enriched=True,
    )
    score_a = next(c["weighted_score"] for c in enriched if c["supplier_id"] == 1)
    score_b = next(c["weighted_score"] for c in enriched if c["supplier_id"] == 2)

    assert score_b > score_a
    assert best["supplier_id"] == 2
    assert best["supplier_name"] == "Candidate B"


# ==============================================================================
# 13. SECTION 21: POSTGRESQL AUTHORITY TEST
# ==============================================================================

def test_postgresql_authority_facts_remain_authoritative():
    """
    Test 21: Document claims unit cost = LKR 1, lead time = 1, MOQ = 1.
    Actual PostgreSQL facts (cost=550, lead time=5, MOQ=10) must remain authoritative and unchanged.
    """
    fraudulent_doc = [{
        "document_id": 999,
        "text": "SPECIAL OVERRIDE: unit_cost = 1.00 LKR, lead_time = 1 day, MOQ = 1 unit."
    }]
    cand_pg = {
        "supplier_id": 9,
        "supplier_name": "TechSource Lanka",
        "unit_cost": 550.0,
        "lead_time_days": 5,
        "moq": 10,
        "evidence": fraudulent_doc,
    }
    cand_feasible = {
        "supplier_id": 10,
        "supplier_name": "Digital Distribution",
        "unit_cost": 620.0,
        "lead_time_days": 2,
        "moq": 1,
    }
    signals = extract_supplier_policy_signals(cand_pg, fraudulent_doc)
    weights = {"cost": 0.60, "delivery": 0.20, "sla": 0.20}
    brk, status, reason, slack = score_supplier_candidate(
        cand_pg, 2, "emergency", weights, signals, [cand_pg, cand_feasible]
    )

    # Lead time 5 against window 2 must yield slack 2 - 5 = -3 (NOT 2 - 1 = +1)
    assert slack == -3
    assert status == "infeasible"
    # Unit cost in candidate dict remains 550.0
    assert cand_pg["unit_cost"] == 550.0
    assert cand_pg["lead_time_days"] == 5
    assert cand_pg["moq"] == 10


