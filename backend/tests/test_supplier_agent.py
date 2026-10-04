"""
Unit and Integration Tests for Member 3: Supplier / Procurement Agent.
Tests fuzzy entity resolution, candidate evaluation, grounding, output validation,
failure modes, and strict boundary enforcement.
"""

import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.session import get_db
from app.database.base import Base
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.document import Document, DocumentType, IndexStatus
from app.core.llm_provider import MockLLMProvider, LLMProviderError
from app.agents.supplier_procurement_agent import SupplierProcurementAgent
from app.schemas.supplier_agent import (
    SupplierAgentRequest,
    SupplierAgentResponse,
)
from app.services.query_understanding_service import (
    resolve_supplier_entity_with_status,
    resolve_product_entity_with_status,
)


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed_agent_data(test_db: Session):
    # 1. Suppliers
    s1 = Supplier(
        id=9,
        supplier_code="DEMO-SUP-001",
        name="TechSource Lanka",
        contact_name="Rohan Silva",
        email="rohan@techsource.lk",
        phone="+94 11 234 5678",
        is_active=True,
    )
    s2 = Supplier(
        id=10,
        supplier_code="DEMO-SUP-002",
        name="Digital Distribution Lanka",
        contact_name="Priyani Perera",
        email="priyani@digitaldist.lk",
        phone="+94 11 345 6789",
        is_active=True,
    )
    s3 = Supplier(
        id=11,
        supplier_code="DEMO-SUP-003",
        name="NextGen Supplies",
        contact_name="Arjun Fernando",
        email="arjun@nextgen.lk",
        phone="+94 11 456 7890",
        is_active=True,
    )

    # 2. Products
    p1 = Product(
        id=1,
        sku="DEMO-001",
        name="Wireless Mouse",
        category="Peripherals",
        unit_price=Decimal("3500.00"),
        reorder_point=25,
        is_active=True,
    )
    p2 = Product(
        id=2,
        sku="DEMO-002",
        name="Mechanical Keyboard",
        category="Peripherals",
        unit_price=Decimal("12500.00"),
        reorder_point=15,
        is_active=True,
    )
    p3 = Product(
        id=3,
        sku="DEMO-003",
        name="USB Cable Type A",
        category="Cables",
        unit_price=Decimal("500.00"),
        reorder_point=50,
        is_active=True,
    )
    p4 = Product(
        id=4,
        sku="DEMO-004",
        name="USB Cable Type B",
        category="Cables",
        unit_price=Decimal("550.00"),
        reorder_point=50,
        is_active=True,
    )

    # 3. Product-Supplier Commercial Offers
    # Wireless Mouse from TechSource: cost=2400, moq=30, lead_time=5
    ps1 = ProductSupplier(
        id=1,
        product_id=1,
        supplier_id=9,
        unit_cost=Decimal("2400.00"),
        moq=30,
        lead_time_days=5,
        is_active=True,
    )
    # Wireless Mouse from Digital Distribution: cost=2550, moq=20, lead_time=2
    ps2 = ProductSupplier(
        id=2,
        product_id=1,
        supplier_id=10,
        unit_cost=Decimal("2550.00"),
        moq=20,
        lead_time_days=2,
        is_active=True,
    )

    # 4. Documents
    d1 = Document(
        id=18,
        title="TechSource Lanka Service Level Agreement",
        document_type=DocumentType.SUPPLIER_SLA.value,
        supplier_id=9,
        original_filename="techsource_sla.pdf",
        storage_key="techsource_sla.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        sha256_checksum="hash1",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
    )

    test_db.add_all([s1, s2, s3, p1, p2, p3, p4, ps1, ps2, d1])
    test_db.commit()


@pytest.fixture
def mock_admin_user(test_db: Session) -> User:
    user = User(
        email="agent_user@example.com",
        name="Agent User",
        role=UserRole.ADMIN.value,
        password_hash="fakehashedpassword",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def client(test_db: Session, mock_admin_user: User):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_current_user():
        return mock_admin_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# =============================================================================
# 1. FUZZY ENTITY RESOLUTION TESTS
# =============================================================================

def test_exact_supplier_and_product_resolution(test_db: Session, seed_agent_data):
    # Exact SKU
    prod, clarify, _ = resolve_product_entity_with_status("DEMO-001", test_db)
    assert clarify is False
    assert prod is not None
    assert prod.name == "Wireless Mouse"

    # Exact Supplier Code
    supp, clarify, _ = resolve_supplier_entity_with_status("DEMO-SUP-001", test_db)
    assert clarify is False
    assert supp is not None
    assert supp.name == "TechSource Lanka"


def test_misspelled_supplier_resolution(test_db: Session, seed_agent_data):
    # 'TechSorce' should resolve to 'TechSource Lanka'
    supp1, clarify1, _ = resolve_supplier_entity_with_status("What are the terms from TechSorce?", test_db)
    assert clarify1 is False
    assert supp1 is not None
    assert supp1.name == "TechSource Lanka"

    # 'Nextgen' should resolve to 'NextGen Supplies'
    supp2, clarify2, _ = resolve_supplier_entity_with_status("Can Nextgen deliver quickly?", test_db)
    assert clarify2 is False
    assert supp2 is not None
    assert supp2.name == "NextGen Supplies"


def test_misspelled_product_resolution(test_db: Session, seed_agent_data):
    # 'wirless mouse' should resolve to 'Wireless Mouse'
    prod, clarify, _ = resolve_product_entity_with_status("Check offers for 60 wirless mouse units", test_db)
    assert clarify is False
    assert prod is not None
    assert prod.name == "Wireless Mouse"
    assert prod.sku == "DEMO-001"


def test_ambiguous_fuzzy_match_requires_clarification(test_db: Session, seed_agent_data):
    # 'USB Cable' matches both 'USB Cable Type A' and 'USB Cable Type B' with very close score
    prod, clarify, matches = resolve_product_entity_with_status("Need quotes for usb cable", test_db)
    assert clarify is True
    assert prod is None
    assert len(matches) >= 2


# =============================================================================
# 2. CANDIDATE BUILDING & MOQ PRESERVATION TESTS
# =============================================================================

def test_candidate_collection_and_authoritative_facts(test_db: Session, seed_agent_data):
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [
            {"supplier_id": 9, "advantages": ["Lowest unit cost"], "risks": ["Longer lead time"]},
            {"supplier_id": 10, "advantages": ["Faster delivery"], "risks": ["Higher cost"]}
        ],
        "advisory_supplier": {"supplier_id": 10, "reason": "Fast delivery in urgent scenarios."},
        "policy_constraints": []
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60, urgency="normal")

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.status == "success"
    assert res.product["name"] == "Wireless Mouse"
    assert res.requested_quantity == 60
    assert len(res.candidate_assessments) == 2

    # Check TechSource Lanka authoritative facts
    c1 = next(c for c in res.candidate_assessments if c.supplier_id == 9)
    assert c1.unit_cost == 2400.0
    assert c1.moq == 30
    assert c1.lead_time_days == 5
    assert c1.meets_moq is True
    assert c1.estimated_cost == 144000.0

    # Check Digital Distribution Lanka authoritative facts
    c2 = next(c for c in res.candidate_assessments if c.supplier_id == 10)
    assert c2.unit_cost == 2550.0
    assert c2.moq == 20
    assert c2.lead_time_days == 2
    assert c2.meets_moq is True
    assert c2.estimated_cost == 153000.0


def test_moq_eligibility_preserves_requested_quantity(test_db: Session, seed_agent_data):
    """
    CRITICAL: If requested_quantity = 20 and MOQ = 30,
    meets_moq must be False, and requested_quantity must NOT be silently changed to 30.
    """
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [
            {"supplier_id": 9, "advantages": [], "risks": ["Below MOQ"]},
            {"supplier_id": 10, "advantages": ["Meets MOQ"], "risks": []}
        ],
        "advisory_supplier": {"supplier_id": 10, "reason": "Only supplier meeting MOQ."},
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=20, urgency="normal")

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.requested_quantity == 20  # NEVER ALTERED
    c1 = next(c for c in res.candidate_assessments if c.supplier_id == 9)
    assert c1.moq == 30
    assert c1.meets_moq is False
    assert c1.estimated_cost == 48000.0  # 2400 * 20, NOT 2400 * 30!

    c2 = next(c for c in res.candidate_assessments if c.supplier_id == 10)
    assert c2.moq == 20
    assert c2.meets_moq is True


def test_missing_quantity_handled_safely(test_db: Session, seed_agent_data):
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [],
        "advisory_supplier": None
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=None)

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.requested_quantity is None
    for c in res.candidate_assessments:
        assert c.meets_moq is None
        assert c.estimated_cost is None
    assert any("MOQ eligibility cannot be fully determined" in w for w in res.warnings)


# =============================================================================
# 3. EVIDENCE GATHERING & LLM GROUNDING TESTS
# =============================================================================

def test_structured_and_ir_evidence_gathered(test_db: Session, seed_agent_data):
    fake_chunk = {
        "document_id": 18,
        "document_title": "TechSource Lanka Service Level Agreement",
        "document_type": "supplier_sla",
        "supplier_id": 9,
        "page_number": 1,
        "chunk_index": 2,
        "text": "Standard lead time is 5 business days with 48h emergency dispatch.",
        "distance": 0.15,
        "source_type": "document_ir",
        "authority": "policy_or_sla",
    }

    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [
            {"supplier_id": 9, "advantages": ["48h emergency dispatch"], "risks": [], "cited_document_ids": [18]}
        ],
        "advisory_supplier": {"supplier_id": 9, "reason": "Emergency dispatch available under SLA."}
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60, urgency="emergency")

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[fake_chunk]):
        res = agent.assess_suppliers(req, test_db)

    c1 = next(c for c in res.candidate_assessments if c.supplier_id == 9)
    assert len(c1.evidence) >= 1
    ev = c1.evidence[0]
    assert ev["document_id"] == 18
    assert ev["title"] == "TechSource Lanka Service Level Agreement"
    assert ev["page_number"] == 1
    assert ev["source_type"] == "document_ir"
    assert ev["authority"] == "policy_or_sla"


def test_emergency_context_passed_to_llm(test_db: Session, seed_agent_data):
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [],
        "advisory_supplier": None
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=50, urgency="emergency")

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        agent.assess_suppliers(req, test_db)

    assert len(mock_llm.call_history) == 1
    call = mock_llm.call_history[0]
    assert "emergency" in call["user_prompt"]
    assert "UNTRUSTED DOCUMENT CONTENT" in call["system_prompt"]


def test_valid_advisory_supplier_output(test_db: Session, seed_agent_data):
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [
            {"supplier_id": 9, "advantages": ["Cheaper"], "risks": []},
            {"supplier_id": 10, "advantages": ["Faster"], "risks": []}
        ],
        "advisory_supplier": {
            "supplier_id": 9,
            "reason": "Offers lowest total procurement cost of LKR 144,000."
        },
        "policy_constraints": ["CFO sign-off required for orders exceeding LKR 500,000."]
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60, urgency="normal")

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.advisory_supplier is not None
    assert res.advisory_supplier.supplier_id == 9
    assert res.advisory_supplier.supplier_name == "TechSource Lanka"
    assert "LKR 144,000" in res.advisory_supplier.reason
    assert res.advisory_only is True


# =============================================================================
# 4. SECURITY & VALIDATION PROTECTIONS
# =============================================================================

def test_llm_cannot_introduce_unknown_supplier(test_db: Session, seed_agent_data):
    """If LLM hallucinates an unknown supplier_id (e.g. 999), it is rejected."""
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [],
        "advisory_supplier": {
            "supplier_id": 999,
            "reason": "Made-up supplier with super low price"
        }
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60)

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.advisory_supplier is None
    assert any("999 not found" in w for w in res.warnings)


def test_llm_cannot_overwrite_postgresql_numeric_facts(test_db: Session, seed_agent_data):
    """Even if LLM prompt tries to change prices, DB authoritative facts prevail."""
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [
            {"supplier_id": 9, "unit_cost": 10.0, "moq": 1, "lead_time_days": 1}
        ],
        "advisory_supplier": {"supplier_id": 9, "reason": "Cheapest"}
    }))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60)

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    c1 = next(c for c in res.candidate_assessments if c.supplier_id == 9)
    # Must remain exact DB value 2400.0, NOT 10.0!
    assert c1.unit_cost == 2400.0
    assert c1.moq == 30
    assert c1.lead_time_days == 5


# =============================================================================
# 5. ERROR HANDLING & DEGRADED FALLBACK
# =============================================================================

def test_malformed_llm_output_triggers_degraded_fallback(test_db: Session, seed_agent_data):
    """When LLM returns non-JSON garbage, system gracefully degrades."""
    mock_llm = MockLLMProvider(default_response="I am an LLM and I refuse to output JSON.")

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60)

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.status == "degraded"
    assert res.advisory_supplier is None
    assert len(res.candidate_assessments) == 2
    assert any("deterministic factual assessment" in w for w in res.warnings)


def test_llm_timeout_triggers_degraded_status(test_db: Session, seed_agent_data):
    """When LLM provider times out or errors, returns degraded response without crash."""
    mock_llm = MockLLMProvider(side_effect=LLMProviderError("Request timed out after 15s"))

    agent = SupplierProcurementAgent(llm_provider=mock_llm)
    req = SupplierAgentRequest(sku="DEMO-001", requested_quantity=60)

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        res = agent.assess_suppliers(req, test_db)

    assert res.status == "degraded"
    assert res.advisory_supplier is None
    assert len(res.candidate_assessments) == 2
    assert res.candidate_assessments[0].unit_cost == 2400.0


# =============================================================================
# 6. MEMBER 4 BOUNDARY & CONTRACT INTEGRITY
# =============================================================================

def test_no_final_reorder_fields_in_schema():
    """Confirms Member 3 does NOT cross Member 4's boundary."""
    fields = SupplierAgentResponse.model_fields
    assert "reorder_decision" not in fields
    assert "final_order_quantity" not in fields
    assert "replenishment_decision" not in fields
    assert "should_replenish" not in fields
    assert fields["advisory_only"].default is True


# =============================================================================
# 7. API ENDPOINT INTEGRATION
# =============================================================================

def test_supplier_agent_api_endpoint(client: TestClient, test_db: Session, seed_agent_data):
    mock_llm = MockLLMProvider(default_response=json.dumps({
        "assessments": [
            {"supplier_id": 9, "advantages": ["Meets MOQ", "Cost-effective"], "risks": []}
        ],
        "advisory_supplier": {"supplier_id": 9, "reason": "Optimal commercial terms."}
    }))

    with patch("app.agents.supplier_procurement_agent.get_llm_provider", return_value=mock_llm), \
         patch("app.services.supplier_knowledge_service.search_documents", return_value=[]):
        payload = {
            "sku": "DEMO-001",
            "requested_quantity": 60,
            "urgency": "normal",
        }
        response = client.post("/api/v1/supplier-agent/assess", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent"] == "supplier_procurement"
        assert data["status"] == "success"
        assert data["product"]["sku"] == "DEMO-001"
        assert len(data["candidate_assessments"]) == 2
        assert data["advisory_supplier"]["supplier_id"] == 9
        assert data["advisory_only"] is True
