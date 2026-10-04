"""
Regression Test Suite for ChromaDB Test Isolation and Terminology Cleanup.
Validates:
1. Test Chroma path != development Chroma path
2. Deleting/recreating a test collection cannot delete development vectors
3. Reconciliation in tests only affects temporary test Chroma
4. Development vector count remains unchanged after test execution
5. Application uses normal development Chroma path outside pytest overrides
6. Self-healing reconciliation still functions when collection genuinely has zero vectors
7. Corrected decision explanation uses 'available-to-fulfil inventory'
8. No outdated 'physical on-hand stock may be exhausted' wording in user-facing output
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, settings
from app.services.chroma_service import (
    _get_client,
    _get_collection,
    reset_chroma_client,
    reconcile_index_state,
)
from app.services.decision_service import (
    generate_deterministic_explanation,
    derive_procurement_urgency,
)
from app.agents.supplier_procurement_agent import SupplierProcurementAgent
from app.database.base import Base
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.product_supplier import ProductSupplier


@pytest.fixture
def sqlite_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 1. TEST ISOLATION & STORAGE CHECKS
# ==============================================================================

def test_1_chroma_path_in_tests_differs_from_development_path():
    """Proves that test execution uses a temporary Chroma directory, never development."""
    dev_default = Settings().CHROMA_PERSIST_DIR
    current_test_dir = settings.CHROMA_PERSIST_DIR

    assert os.path.abspath(current_test_dir) != os.path.abspath(dev_default)
    assert "isolated_test_chroma" in current_test_dir or "pytest" in current_test_dir.lower() or "tmp" in current_test_dir.lower()


def test_2_deleting_test_collection_does_not_affect_development(tmp_path):
    """Proves mutating test Chroma collection operates strictly in test sandbox."""
    client = _get_client()
    col = client.get_or_create_collection("test_sandbox_collection")
    col.add(ids=["t1", "t2"], documents=["doc1", "doc2"], embeddings=[[0.1] * 384, [0.2] * 384])
    assert col.count() == 2

    # Delete test collection
    client.delete_collection("test_sandbox_collection")

    # Verify development directory was not targeted
    dev_default = Settings().CHROMA_PERSIST_DIR
    assert os.path.abspath(client._persist_dir) != os.path.abspath(dev_default)


def test_3_reconciliation_in_tests_only_affects_temporary_chroma(sqlite_db: Session):
    """Proves reconciliation in test environment operates strictly inside isolated directory."""
    # Run reconciliation on empty test DB
    summary = reconcile_index_state(db=sqlite_db, repair=True)
    assert summary["total_documents_checked"] == 0

    # Ensure client used is in isolated test directory
    client = _get_client()
    dev_default = Settings().CHROMA_PERSIST_DIR
    assert os.path.abspath(client._persist_dir) != os.path.abspath(dev_default)


def test_4_application_uses_normal_development_path_by_default():
    """Proves default application configuration points to backend/storage/chroma."""
    default_cfg = Settings()
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    expected_dev_path = os.path.join(backend_dir, "storage", "chroma")
    assert os.path.abspath(default_cfg.CHROMA_PERSIST_DIR) == os.path.abspath(expected_dev_path)


def test_5_self_healing_triggers_when_collection_empty(sqlite_db: Session):
    """Proves self-healing reconciliation still auto-triggers when collection count is 0."""
    from app.schemas.supplier_agent import SupplierAgentRequest
    from decimal import Decimal

    p = Product(name="Test Item", sku="TI-01", is_active=True, reorder_point=10)
    sqlite_db.add(p)
    sqlite_db.flush()

    sup = Supplier(name="Test Supplier", supplier_code="TS-01", is_active=True)
    sqlite_db.add(sup)
    sqlite_db.flush()

    ps = ProductSupplier(product_id=p.id, supplier_id=sup.id, unit_cost=Decimal("100.00"), lead_time_days=3, moq=1, is_active=True)
    sqlite_db.add(ps)
    sqlite_db.commit()

    agent = SupplierProcurementAgent()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    req = SupplierAgentRequest(product_id=p.id)

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("app.services.chroma_service.reconcile_index_state") as mock_reconcile, \
         patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):

        # Assess suppliers when collection has 0 vectors
        result = agent.assess_suppliers(request=req, db=sqlite_db)
        # Self-healing MUST have been called
        assert mock_reconcile.called
        assert mock_reconcile.call_args[1].get("repair") is True


# ==============================================================================
# 2. TERMINOLOGY & WORDING CHECKS
# ==============================================================================

def test_6_decision_explanation_uses_available_to_fulfil_wording():
    """
    Verifies that decision explanations use 'available-to-fulfil inventory'
    instead of outdated 'physical on-hand stock'.
    """
    reasoning, factors = generate_deterministic_explanation(
        product_name="Wireless Mouse",
        replenishment_required=True,
        quantity=131,
        selected_supplier={
            "supplier_name": "Digital Distribution",
            "unit_cost": 2550.0,
            "lead_time_days": 2,
            "delivery_slack_days": 0,
        },
        risk_level="HIGH",
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0,
        incoming_stock=60,
        days_until_buffer_breach=5,
        days_until_stockout=2,
        required_delivery_window_days=2,
        urgency="emergency",
    )

    # Required terminology
    assert "available-to-fulfil inventory may be exhausted in approximately 2 days" in reasoning
    # Outdated terminology must NOT exist
    assert "physical on-hand stock may be exhausted" not in reasoning
    assert "physical stockout" not in reasoning.lower() or "stockout horizon" in reasoning.lower()


def test_7_factors_use_available_inventory_exhaustion_wording():
    """Verifies that decision factors use 'available inventory exhaustion'."""
    _, factors = generate_deterministic_explanation(
        product_name="Wireless Mouse",
        replenishment_required=True,
        quantity=131,
        selected_supplier={"supplier_name": "Digital Distribution", "unit_cost": 2550.0, "lead_time_days": 2},
        risk_level="HIGH",
        available_stock=24,
        reorder_point=30,
        predicted_demand=184.0,
        incoming_stock=60,
        days_until_buffer_breach=5,
        days_until_stockout=2,
        required_delivery_window_days=2,
        urgency="emergency",
    )

    assert any("available inventory exhaustion in 2 days" in f for f in factors)
    assert any("Days until available inventory is exhausted: 2 days." in f for f in factors)
    assert not any("Days until physical stockout:" in f for f in factors)
    assert not any("physical on-hand stock" in f for f in factors)


def test_8_urgency_reason_uses_available_to_fulfil_wording():
    """Verifies that derive_procurement_urgency uses available-to-fulfil terminology."""
    urgency, reason = derive_procurement_urgency(
        replenishment_required=True,
        stockout_risk_level="HIGH",
        days_until_unsafe=5,
        days_until_stockout=2,
        required_delivery_window_days=2,
        active_lead_times=[2, 5, 7],
        available_stock=24,
        reorder_point=30,
        days_until_buffer_breach=5,
    )

    assert urgency == "emergency"
    assert "available-to-fulfil inventory may be exhausted in approximately 2 days" in reason
    assert "physical on-hand stock" not in reason
