"""
Focused test suite for SmartSupply Replenishment Business Logic Fixes.
Validates:
1. incoming=0 preserves expected previous behavior.
2. Incoming stock reduces required quantity (e.g. 24 avail + 60 incoming + 184 forecast + 30 ROP -> 131).
3. Sufficient incoming prevents unnecessary replenishment (e.g. 20 avail + 100 incoming + 40 forecast + 25 ROP -> False).
4. Partial incoming still results in a correct shortage.
5. Negative incoming is safely treated as 0.
6. Reorder point remains the effective safety-stock buffer.
7. No separate safety-stock calculation or database column is introduced.
8. Supplier MOQ increases quantity only when necessary.
9. Forecast above current stock but fully covered by incoming stock does not incorrectly trigger another order.
10. Decision API and snapshots expose/explain incoming and effective inventory correctly.
11. DEMO-001 Digital Distribution synthetic fixture uses 2550 / MOQ 20 / 2 days.
12. End-to-end integration and arithmetic integrity.
"""

from decimal import Decimal
import math
from typing import Any, Dict
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.schemas.decision import (
    DecisionRecommendationRequest,
    DecisionRecommendationResponse,
    InventorySnapshot,
)
from app.services.decision_service import (
    calculate_replenishment_shortage,
    generate_deterministic_explanation,
    select_best_supplier_candidate,
)


@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(sqlite_engine):
    TestingSession = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    session = TestingSession()
    yield session
    session.rollback()
    session.close()


# =========================================================================
# 1. INCOMING=0 PRESERVES PREVIOUS BEHAVIOR
# =========================================================================
def test_1_incoming_zero_preserves_previous_behavior():
    """When incoming=0, calculation matches traditional (demand + ROP) - available."""
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0006,
        incoming_stock=0,
    )

    assert rep is True
    assert metrics["effective_inventory"] == 24
    assert metrics["effective_safety_stock"] == 30
    assert metrics["net_requirement"] == 190.0006
    assert qty == 191  # ceil(190.0006) = 191


# =========================================================================
# 2. INCOMING STOCK REDUCES REQUIRED QUANTITY
# =========================================================================
def test_2_incoming_stock_reduces_required_quantity():
    """
    DEMO-001 baseline:
    available=24, incoming=60, forecast=184.0006, ROP=30
    effective_inventory = 24 + 60 = 84
    net_requirement = 184.0006 + 30 - 84 = 130.0006
    raw_quantity = ceil(130.0006) = 131
    """
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0006,
        incoming_stock=60,
    )

    assert rep is True
    assert metrics["available_stock"] == 24
    assert metrics["incoming_stock"] == 60
    assert metrics["effective_inventory"] == 84
    assert metrics["reorder_point"] == 30
    assert metrics["effective_safety_stock"] == 30
    assert metrics["net_requirement"] == 130.0006
    assert qty == 131


# =========================================================================
# 3. SUFFICIENT INCOMING PREVENTS UNNECESSARY REPLENISHMENT
# =========================================================================
def test_3_sufficient_incoming_prevents_unnecessary_replenishment():
    """
    Example from requirements:
    available = 20, incoming = 100, forecast = 40, ROP = 25
    effective_inventory = 120
    required position = 40 + 25 = 65
    net_requirement = 65 - 120 = -55
    Result: replenishment_required = False, qty = 0.
    Must NOT trigger simply because available_stock (20) <= ROP (25).
    """
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=20,
        reorder_point=25,
        predicted_demand=40.0,
        incoming_stock=100,
    )

    assert rep is False
    assert qty == 0
    assert metrics["effective_inventory"] == 120
    assert metrics["net_requirement"] == -55.0
    assert metrics["has_shortage"] is False
    assert metrics["is_effective_low_stock"] is False


# =========================================================================
# 4. PARTIAL INCOMING STILL RESULTS IN A CORRECT SHORTAGE
# =========================================================================
def test_4_partial_incoming_results_in_correct_shortage():
    """
    available = 20, incoming = 15, forecast = 40, ROP = 25
    effective_inventory = 35
    required position = 40 + 25 = 65
    net_requirement = 65 - 35 = 30
    Result: replenishment_required = True, raw_quantity = 30.
    """
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=20,
        reorder_point=25,
        predicted_demand=40.0,
        incoming_stock=15,
    )

    assert rep is True
    assert qty == 30
    assert metrics["effective_inventory"] == 35
    assert metrics["net_requirement"] == 30.0


# =========================================================================
# 5. NEGATIVE INCOMING IS SAFELY TREATED AS 0
# =========================================================================
def test_5_negative_incoming_safely_treated_as_zero():
    """Corrupt or negative incoming values must be clamped to 0 defensively."""
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0006,
        incoming_stock=-20,
    )

    assert rep is True
    assert metrics["incoming_stock"] == 0
    assert metrics["effective_inventory"] == 24
    assert qty == 191


# =========================================================================
# 6. REORDER POINT REMAINS THE EFFECTIVE SAFETY-STOCK BUFFER
# =========================================================================
def test_6_reorder_point_remains_effective_safety_stock_buffer():
    """
    When demand is 0 and available stock is below ROP:
    available = 10, incoming = 0, ROP = 25, demand = 0
    net_requirement = 0 + 25 - 10 = 15
    Result: replenishment_required = True, raw_quantity = 15.
    Directly restores stock to the ROP buffer.
    """
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=10,
        reorder_point=25,
        predicted_demand=0.0,
        incoming_stock=0,
    )

    assert rep is True
    assert qty == 15
    assert metrics["effective_safety_stock"] == 25
    assert metrics["net_requirement"] == 15.0


# =========================================================================
# 7. NO SEPARATE SAFETY STOCK CALCULATION OR DB COLUMN
# =========================================================================
def test_7_no_separate_safety_stock_calculation(sqlite_engine):
    """Verifies architectural constraint: no separate safety_stock DB column."""
    insp = inspect(sqlite_engine)
    product_cols = [c["name"] for c in insp.get_columns("products")]
    inventory_cols = [c["name"] for c in insp.get_columns("inventory")]

    assert "safety_stock" not in product_cols
    assert "safety_stock" not in inventory_cols
    assert "reorder_point" in product_cols
    assert "incoming" in inventory_cols


# =========================================================================
# 8. SUPPLIER MOQ INCREASES QUANTITY ONLY WHEN NECESSARY
# =========================================================================
def test_8_supplier_moq_logic():
    """
    MOQ should clamp upward when raw_quantity < MOQ,
    but leave raw_quantity intact when raw_quantity >= MOQ.
    """
    candidates = [
        {
            "supplier_id": 1,
            "supplier_name": "Test Supplier",
            "unit_cost": 2000.0,
            "moq": 50,
            "lead_time_days": 5,
        }
    ]

    # Case A: raw_quantity (131) >= MOQ (50) -> remains 131
    _, final_qty_a, _, _ = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=131,
        urgency="normal",
    )
    assert final_qty_a == 131

    # Case B: raw_quantity (18) < MOQ (50) -> adjusted to 50
    _, final_qty_b, _, factors = select_best_supplier_candidate(
        candidates=candidates,
        recommended_quantity=18,
        urgency="normal",
    )
    assert final_qty_b == 50
    assert any("adjusted up to 50" in f for f in factors)


# =========================================================================
# 9. FORECAST ABOVE CURRENT STOCK FULLY COVERED BY INCOMING NO REORDER
# =========================================================================
def test_9_forecast_above_current_stock_covered_by_incoming():
    """
    available = 30, ROP = 20 (available > ROP)
    forecast = 50 (forecast > available)
    incoming = 60
    effective_inventory = 30 + 60 = 90
    required position = 50 + 20 = 70
    net_requirement = 70 - 90 = -20
    Result: replenishment_required = False, raw_quantity = 0.
    """
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=30,
        reorder_point=20,
        predicted_demand=50.0,
        incoming_stock=60,
    )

    assert rep is False
    assert qty == 0
    assert metrics["effective_inventory"] == 90
    assert metrics["net_requirement"] == -20.0


# =========================================================================
# 10. DECISION EXPLANATION EXPOSES INCOMING AND EFFECTIVE INVENTORY
# =========================================================================
def test_10_decision_explanation_and_snapshot():
    """Verifies that explanations and factors explicitly document pipeline inventory."""
    reasoning, factors = generate_deterministic_explanation(
        product_name="Wireless Mouse",
        replenishment_required=True,
        quantity=131,
        selected_supplier={
            "supplier_name": "NextGen Supplies",
            "unit_cost": 2300.0,
            "lead_time_days": 7,
        },
        risk_level="HIGH",
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0006,
        incoming_stock=60,
        raw_quantity=131,
        net_requirement=130.0006,
    )

    assert "84 units" in reasoning
    assert "24 units" in reasoning
    assert "60 units are confirmed incoming" in reasoning
    assert "131 units" in reasoning
    assert any("Effective inventory position: 84 units" in f for f in factors)
    assert any("60 incoming units were included as confirmed pipeline inventory" in f for f in factors)
    assert any("130.0006 units (rounded up using ceil() to 131 units)" in f for f in factors)


# =========================================================================
# 11. DEMO-001 DIGITAL DISTRIBUTION FIXTURE VERIFICATION
# =========================================================================
def test_11_demo_001_digital_distribution_fixture_aligned():
    """Confirms test_supplier_agent.py fixture matches canonical PostgreSQL seed data."""
    import inspect as py_inspect
    from tests import test_supplier_agent

    source = py_inspect.getsource(test_supplier_agent.seed_agent_data)
    assert 'Decimal("2550.00")' in source
    assert "2600" not in source
    assert "lead_time_days=2" in source


# =========================================================================
# 12. FLOATING-POINT CEIL CLARITY VERIFICATION
# =========================================================================
def test_12_ceil_rounding_clarity():
    """Verifies ceil() protects against stockout without silent truncation."""
    rep, qty, metrics = calculate_replenishment_shortage(
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0006,
        incoming_stock=60,
    )

    assert math.isclose(metrics["net_requirement"], 130.0006, abs_tol=1e-4)
    assert qty == 131
    assert qty > metrics["net_requirement"]
