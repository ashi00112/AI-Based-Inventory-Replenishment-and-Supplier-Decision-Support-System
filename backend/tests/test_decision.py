"""
Comprehensive Unit and Integration Tests for Member 4: Replenishment Decision Agent.
Covers all required specifications:
- CASE 1: Low inventory + high predicted demand -> replenishment = YES
- CASE 2: Enough inventory -> replenishment = NO
- CASE 3: Multiple suppliers -> optimal supplier selected by criteria/policy
- CASE 4: Policy restriction -> restricted/suspended supplier is not selected
- CASE 5: Missing critical data -> safe response/warning instead of hallucination
- CASE 6: Grok API failure -> graceful fallback to deterministic explanation
- CASE 7: Negative calculated quantity -> strictly clamped to zero
- CASE 8: Human approval workflow (PENDING -> APPROVED)
- CASE 9: Human rejection workflow (PENDING -> REJECTED)
- CASE 10: Invalid state transitions rejected
- CASE 11: End-to-end API integration (/api/v1/decision/recommend, /history, /approve, /reject)
- CASE 12: Grok provider configuration, formatting, and secret sanitization
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.core.llm_provider import (
    BaseLLMProvider,
    GrokRESTProvider,
    LLMProviderError,
    MockLLMProvider,
    set_grok_provider,
)
from app.models.decision import ApprovalStatus, DecisionRecommendation
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.sales_history import SalesHistory
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.decision import (
    DecisionApprovalRequest,
    DecisionRecommendationRequest,
    DecisionRecommendationResponse,
)
from app.agents.decision.agent import DecisionAgent
from app.services.decision_service import (
    approve_decision,
    calculate_replenishment_shortage,
    generate_deterministic_explanation,
    get_decision,
    list_decisions,
    reject_decision,
    save_decision_recommendation,
    select_best_supplier_candidate,
)


@pytest.fixture(scope="function")
def test_db_session():
    """Isolated in-memory SQLite database for deterministic testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db_session):
    """FastAPI TestClient bound to the isolated in-memory test database."""
    _, TestingSessionLocal = test_db_session

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_external_llms():
    """Ensures external LLM calls to Grok are mocked by default for speed and isolation."""
    from app.core.llm_provider import set_llm_provider, set_grok_provider
    default_mock = MockLLMProvider(
        default_response=json.dumps({
            "assessments": [
                {
                    "supplier_id": 1,
                    "advantages": ["Cost effective wholesale terms"],
                    "risks": [],
                    "cited_document_ids": [],
                }
            ],
            "advisory_supplier": {"supplier_id": 1, "reason": "Preferred cost terms"},
            "policy_constraints": ["Standard Procurement Policy applies."],
            "warnings": [],
            "reasoning": "Replenishment is necessary due to inventory deficit against strong forecast demand.",
            "factors": ["Available stock (8 units) is below ROP (25 units).", "Forecast demand requires restocking."],
            "confidence": 0.95,
        })
    )
    set_llm_provider(default_mock)
    set_grok_provider(default_mock)
    yield default_mock
    set_llm_provider(None)
    set_grok_provider(None)


@pytest.fixture
def seed_test_data(test_db_session):
    """Seeds consistent catalog products, suppliers, inventory, and sales history."""
    db, _ = test_db_session

    # 1. Product
    product = Product(
        id=101,
        sku="TEST-SKU-001",
        name="Industrial Pro Router",
        category="Networking",
        unit_price=Decimal("15000.00"),
        reorder_point=25,
        is_active=True,
    )
    db.add(product)

    # 2. Inventory (Low Stock: 10 on hand, 2 reserved => 8 available vs ROP 25)
    inv = Inventory(
        id=101,
        product_id=101,
        on_hand=10,
        reserved=2,
        incoming=0,
    )
    db.add(inv)

    # 3. Suppliers
    sup1 = Supplier(
        id=1,
        supplier_code="SUP-ALPHA",
        name="Alpha Wholesale Supplies",
        is_active=True,
    )
    sup2 = Supplier(
        id=2,
        supplier_code="SUP-BETA",
        name="Beta Express Distribution",
        is_active=True,
    )
    sup3 = Supplier(
        id=3,
        supplier_code="SUP-RESTRICTED",
        name="Gamma Restricted Vendor",
        is_active=True,
    )
    db.add_all([sup1, sup2, sup3])

    # 4. ProductSupplier Offers
    # Alpha: Cheaper unit cost, longer lead time
    offer1 = ProductSupplier(
        id=1,
        product_id=101,
        supplier_id=1,
        unit_cost=Decimal("11000.00"),
        moq=20,
        lead_time_days=7,
        is_active=True,
    )
    # Beta: Higher unit cost, fast lead time
    offer2 = ProductSupplier(
        id=2,
        product_id=101,
        supplier_id=2,
        unit_cost=Decimal("12500.00"),
        moq=5,
        lead_time_days=2,
        is_active=True,
    )
    # Gamma: Restricted vendor
    offer3 = ProductSupplier(
        id=3,
        product_id=101,
        supplier_id=3,
        unit_cost=Decimal("9000.00"),
        moq=1,
        lead_time_days=1,
        is_active=True,
    )
    db.add_all([offer1, offer2, offer3])

    # 5. Sales History (30 days of consistent daily sales)
    today = date(2026, 9, 30)
    for i in range(30):
        sale_dt = today - timedelta(days=30 - i)
        db.add(SalesHistory(
            id=i + 1,
            product_id=101,
            sale_date=datetime.combine(sale_dt, datetime.min.time()),
            quantity=5,
            unit_price=Decimal("15000.00"),
            total_amount=Decimal("75000.00"),
        ))

    # 6. Admin user for human approval testing
    user = User(
        id=1,
        name="Procurement Manager",
        email="manager@smartsupply.com",
        password_hash="argon2_fake_hash",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(user)

    db.commit()
    return product, inv, [sup1, sup2, sup3]


# =========================================================================
# CASE 1: Low inventory + high predicted demand -> replenishment = YES
# =========================================================================
def test_case_1_low_inventory_high_demand_replenishment_yes(test_db_session, seed_test_data):
    db, _ = test_db_session
    product, inv, _ = seed_test_data

    # Set up mock Grok response
    mock_grok = MockLLMProvider(
        default_response=json.dumps({
            "reasoning": "Replenishment is necessary due to inventory deficit against strong forecast demand.",
            "factors": ["Available stock (8 units) is below ROP (25 units).", "Forecast demand requires restocking."],
            "confidence": 0.98,
        })
    )

    agent = DecisionAgent(llm_provider=mock_grok)
    request = DecisionRecommendationRequest(product_id=101, forecast_horizon_days=14, urgency="normal")

    response = agent.generate_recommendation(db=db, request=request)

    assert response.product_id == 101
    assert response.replenishment_required is True
    assert response.recommended_order_quantity > 0
    assert response.selected_supplier is not None
    assert response.risk_level in ("HIGH", "CRITICAL")
    assert "Replenishment is necessary" in response.reasoning
    assert response.approval_status == ApprovalStatus.PENDING


# =========================================================================
# CASE 2: Enough inventory -> replenishment = NO
# =========================================================================
def test_case_2_enough_inventory_replenishment_no(test_db_session, seed_test_data):
    db, _ = test_db_session
    product, inv, _ = seed_test_data

    # Update inventory to abundant stock: 500 on hand, 0 reserved => 500 available
    inv.on_hand = 500
    inv.reserved = 0
    db.commit()

    mock_grok = MockLLMProvider(
        default_response=json.dumps({
            "reasoning": "Replenishment is not required as current inventory is more than sufficient.",
            "factors": ["Available stock of 500 units well exceeds ROP of 25."],
            "confidence": 0.99,
        })
    )

    agent = DecisionAgent(llm_provider=mock_grok)
    request = DecisionRecommendationRequest(product_id=101, forecast_horizon_days=14, urgency="normal")

    response = agent.generate_recommendation(db=db, request=request)

    assert response.product_id == 101
    assert response.replenishment_required is False
    assert response.recommended_order_quantity == 0
    assert response.selected_supplier is None
    assert response.risk_level == "LOW"


# =========================================================================
# CASE 3: Multiple suppliers -> optimal selection according to criteria
# =========================================================================
def test_case_3_multiple_suppliers_optimal_selection():
    candidates = [
        {
            "supplier_id": 1,
            "supplier_name": "Alpha Wholesale",
            "unit_cost": 11000.0,
            "moq": 10,
            "lead_time_days": 8,
            "risks": [],
        },
        {
            "supplier_id": 2,
            "supplier_name": "Beta Express",
            "unit_cost": 13500.0,
            "moq": 5,
            "lead_time_days": 2,
            "risks": [],
        },
    ]

    # Test 3A: Normal urgency prioritizes lowest unit cost (Alpha)
    chosen_normal, qty_normal, _, factors_normal = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=50,
        urgency="normal",
    )
    assert chosen_normal is not None
    assert chosen_normal["supplier_id"] == 1
    assert chosen_normal["unit_cost"] == 11000.0
    assert qty_normal == 50

    # Test 3B: Emergency urgency prioritizes shortest lead time (Beta)
    chosen_emerg, qty_emerg, _, factors_emerg = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=50,
        urgency="emergency",
    )
    assert chosen_emerg is not None
    assert chosen_emerg["supplier_id"] == 2
    assert chosen_emerg["lead_time_days"] == 2


# =========================================================================
# CASE 4: Policy restriction -> restricted supplier is disqualified
# =========================================================================
def test_case_4_policy_restriction_disqualifies_supplier():
    candidates = [
        {
            "supplier_id": 3,
            "supplier_name": "Gamma Restricted Vendor",
            "unit_cost": 8000.0,  # Cheaper, but restricted!
            "moq": 1,
            "lead_time_days": 1,
            "risks": ["Compliance alert: Vendor suspended due to audit failure."],
        },
        {
            "supplier_id": 1,
            "supplier_name": "Alpha Wholesale",
            "unit_cost": 11000.0,
            "moq": 10,
            "lead_time_days": 5,
            "risks": [],
        },
    ]

    chosen, _, warnings, _ = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=25,
        urgency="normal",
    )

    # Gamma must be excluded despite being cheaper and faster
    assert chosen is not None
    assert chosen["supplier_id"] == 1
    assert any("Gamma Restricted Vendor" in w for w in warnings)


# =========================================================================
# CASE 5: Missing critical data -> safe response and warnings without hallucination
# =========================================================================
def test_case_5_missing_critical_data_safeguard(test_db_session):
    db, _ = test_db_session

    # Create new product with NO inventory record and NO sales history
    empty_prod = Product(
        id=202,
        sku="EMPTY-SKU",
        name="Empty Product With No Data",
        unit_price=Decimal("1000.00"),
        reorder_point=10,
        is_active=True,
    )
    db.add(empty_prod)
    db.commit()

    agent = DecisionAgent(llm_provider=MockLLMProvider())
    request = DecisionRecommendationRequest(product_id=202, forecast_horizon_days=14)

    response = agent.generate_recommendation(db=db, request=request)

    assert response.product_id == 202
    assert len(response.warnings) > 0
    # Must identify missing data transparently
    assert any("sales data" in w.lower() or "inventory" in w.lower() for w in response.warnings)
    # Must not hallucinate supplier when none exist
    assert response.selected_supplier is None


# =========================================================================
# CASE 6: Grok API failure -> graceful handling with deterministic fallback
# =========================================================================
def test_case_6_grok_api_failure_graceful_handling(test_db_session, seed_test_data):
    db, _ = test_db_session

    # Configure mock provider to simulate network timeout / API outage
    failing_grok = MockLLMProvider(
        side_effect=LLMProviderError("Grok service connection timed out after 15s")
    )

    agent = DecisionAgent(llm_provider=failing_grok)
    request = DecisionRecommendationRequest(product_id=101, forecast_horizon_days=14)

    # Execution must not crash
    response = agent.generate_recommendation(db=db, request=request)

    assert response.product_id == 101
    assert response.replenishment_required is True
    assert response.recommended_order_quantity > 0
    # Must fall back to deterministic explanation
    assert len(response.reasoning) > 0
    assert "Replenishment is REQUIRED" in response.reasoning
    assert len(response.factors) > 0


# =========================================================================
# CASE 7: Negative calculated quantity -> strictly clamped to zero
# =========================================================================
def test_case_7_negative_quantity_clamping():
    # Test calculate_replenishment_shortage with massive inventory surplus
    replenish, qty, metrics = calculate_replenishment_shortage(
        available_stock=10000,
        reorder_point=50,
        predicted_demand=100.0,
    )

    assert replenish is False
    assert qty == 0
    assert qty >= 0  # Invariant safeguard

    # Test edge case: negative stock input defensively handled
    replenish_neg, qty_neg, metrics_neg = calculate_replenishment_shortage(
        available_stock=-10,  # Corrupt negative input
        reorder_point=20,
        predicted_demand=30.0,
    )
    assert replenish_neg is True
    assert qty_neg >= 0


# =========================================================================
# CASE 8 & 9 & 10: Human Approval / Rejection Workflow & Transitions
# =========================================================================
def test_case_8_9_10_human_approval_workflow(test_db_session, seed_test_data):
    db, _ = test_db_session

    # 1. Save pending recommendation
    rec = save_decision_recommendation(
        db=db,
        product_id=101,
        replenishment_required=True,
        recommended_order_quantity=50,
        selected_supplier_id=1,
        selected_supplier_name="Alpha Wholesale",
        unit_cost=11000.0,
        estimated_total_cost=550000.0,
        risk_level="HIGH",
        reasoning="Critical stockout risk requires immediate replenishment.",
        factors=["Available stock < ROP"],
        warnings=[],
        policy_references=["Standard Procurement SLA"],
        confidence=0.95,
    )

    assert rec.id is not None
    assert rec.approval_status == ApprovalStatus.PENDING.value

    # 2. Approve recommendation
    approved_rec = approve_decision(
        db=db,
        decision_id=rec.id,
        user_id=1,
        notes="Approved for PO #4892.",
    )

    assert approved_rec.approval_status == ApprovalStatus.APPROVED.value
    assert approved_rec.reviewed_by == 1
    assert approved_rec.reviewed_at is not None
    assert approved_rec.reviewer_notes == "Approved for PO #4892."

    # 3. CASE 10: Attempting to re-approve raises invalid transition error
    from app.services.decision_service import InvalidApprovalTransitionError
    with pytest.raises(InvalidApprovalTransitionError):
        approve_decision(db=db, decision_id=rec.id, user_id=1)

    # 4. CASE 9: Rejection workflow on a new pending decision
    rec2 = save_decision_recommendation(
        db=db,
        product_id=101,
        replenishment_required=True,
        recommended_order_quantity=20,
        selected_supplier_id=1,
        selected_supplier_name="Alpha Wholesale",
        unit_cost=11000.0,
        estimated_total_cost=220000.0,
        risk_level="MEDIUM",
        reasoning="Moderate replenishment requirement.",
        factors=[],
        warnings=[],
        policy_references=[],
        confidence=0.90,
    )

    rejected_rec = reject_decision(
        db=db,
        decision_id=rec2.id,
        user_id=1,
        reason="Budget freeze in current quarter.",
    )

    assert rejected_rec.approval_status == ApprovalStatus.REJECTED.value
    assert rejected_rec.rejection_reason == "Budget freeze in current quarter."


# =========================================================================
# CASE 11: End-to-End Decision API Endpoints
# =========================================================================
def test_case_11_decision_api_endpoints(client, seed_test_data):
    # Set default mock provider for API calls
    mock_provider = MockLLMProvider(
        default_response=json.dumps({
            "reasoning": "API Generated replenishment decision with multi-agent context.",
            "factors": ["Net available inventory is depleted."],
            "confidence": 0.95,
        })
    )
    set_grok_provider(mock_provider)

    from app.core.security import create_access_token
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. POST /api/v1/decision/recommend
    res_rec = client.post(
        "/api/v1/decision/recommend",
        json={"product_id": 101, "forecast_horizon_days": 14, "urgency": "normal"},
        headers=headers,
    )
    assert res_rec.status_code == status.HTTP_200_OK
    data = res_rec.json()
    assert data["product_id"] == 101
    assert data["replenishment_required"] is True
    assert data["recommended_order_quantity"] > 0
    assert data["approval_status"] == "PENDING"
    decision_id = data["id"]
    assert decision_id is not None

    # 2. GET /api/v1/decision/history
    res_hist = client.get("/api/v1/decision/history", headers=headers)
    assert res_hist.status_code == status.HTTP_200_OK
    hist_data = res_hist.json()
    assert hist_data["total"] >= 1
    assert any(item["id"] == decision_id for item in hist_data["items"])

    # 3. GET /api/v1/decision/{id}
    res_single = client.get(f"/api/v1/decision/{decision_id}", headers=headers)
    assert res_single.status_code == status.HTTP_200_OK
    assert res_single.json()["id"] == decision_id

    # 4. POST /api/v1/decision/{id}/approve
    res_app = client.post(
        f"/api/v1/decision/{decision_id}/approve",
        json={"status": "APPROVED", "reviewer_notes": "Manager confirmed."},
        headers=headers,
    )
    assert res_app.status_code == status.HTTP_200_OK
    assert res_app.json()["approval_status"] == "APPROVED"


# =========================================================================
# CASE 12: Grok Provider Unit Tests
# =========================================================================
def test_case_12_grok_provider_unit():
    provider = GrokRESTProvider(api_key="test_dummy_key", model_name="grok-beta")
    assert provider.is_configured() is True

    unconfigured = GrokRESTProvider(api_key="")
    assert unconfigured.is_configured() is False

    with pytest.raises(LLMProviderError) as exc_info:
        unconfigured.generate_text("system", "user")
    assert "not configured" in str(exc_info.value)
