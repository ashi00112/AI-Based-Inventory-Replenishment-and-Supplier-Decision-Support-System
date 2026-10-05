"""
Comprehensive Verification Test Suite for Document IR Hardening and Evidence Propagation.
Covers the 12 required criteria:
1. PostgreSQL indexed + Chroma empty -> health = degraded.
2. Missing vectors + source PDF available -> reconciliation can restore index.
3. Missing vectors + source PDF missing -> safe degraded state; no crash.
4. Inactive/deleted doc vectors are purged.
5. Wrong index_version triggers appropriate repair state.
6. Reconciliation is idempotent.
7. Demo bootstrap is idempotent.
8. Final DecisionRecommendationResponse includes evidence.
9. Evidence document IDs/pages/text match SupplierAgent evidence.
10. No fake citations appear.
11. PostgreSQL commercial values remain unchanged by document evidence.
12. Existing supplier-selection and decision tests still pass.
"""

import os
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.core.config import settings
from app.models.document import Document, DocumentType, IndexStatus
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.decision import (
    DecisionRecommendationRequest,
    DecisionRecommendationResponse,
    SupplierCandidateOption,
)
from app.schemas.document_processing import DocumentChunkResponse, DocumentSearchResult
from app.schemas.supplier_agent import CandidateAssessment, SupplierAgentResponse
from app.services.chroma_service import (
    check_document_ir_health,
    reconcile_index_state,
)
from scripts.bootstrap_document_ir import bootstrap_document_ir


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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_admin(test_db: Session) -> User:
    user = User(
        email="admin_hardening@example.com",
        name="Admin Hardening",
        role=UserRole.ADMIN.value,
        password_hash="fakehash",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def client(test_db: Session, mock_admin: User, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path / "documents"))

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_current_user():
        return mock_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# =============================================================================
# 1. PostgreSQL indexed + Chroma empty -> health = degraded
# =============================================================================
def test_1_db_indexed_chroma_empty_reports_degraded(client: TestClient, test_db: Session):
    doc = Document(
        title="Test Doc 1",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="doc1.pdf",
        storage_key="doc1.pdf",
        mime_type="application/pdf",
        file_size_bytes=120,
        sha256_checksum="abc1",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
    )
    test_db.add(doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.count.return_value = 0  # Chroma is empty on fresh clone

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("app.services.embedding_service.EmbeddingProvider.embed_texts", return_value=[[0.1] * 384]), \
         patch("os.path.isfile", return_value=True):
        response = client.get("/api/v1/health/document-ir")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "degraded"
        assert data["vector_count"] == 0
        assert data["active_document_count"] == 1
        assert "0 vectors" in data["details"]


# =============================================================================
# 2. Missing vectors + source PDF available -> reconciliation can restore index
# =============================================================================
def test_2_missing_vectors_source_pdf_available_restores_index(test_db: Session):
    doc = Document(
        title="Restorable Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="doc2.pdf",
        storage_key="doc2.pdf",
        mime_type="application/pdf",
        file_size_bytes=150,
        sha256_checksum="abc2",
        is_active=True,
        index_status=IndexStatus.NOT_INDEXED.value,
    )
    test_db.add(doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": [], "metadatas": []}

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("os.path.isfile", return_value=True), \
         patch("app.services.chroma_service.auto_index_document", return_value=True) as mock_auto_index:
        summary = reconcile_index_state(db=test_db, repair=True)
        assert summary["reindexed_count"] == 1
        assert summary["missing_source_count"] == 0
        mock_auto_index.assert_called_once_with(db=test_db, document_id=doc.id)


# =============================================================================
# 3. Missing vectors + source PDF missing -> safe degraded state; no crash
# =============================================================================
def test_3_missing_vectors_and_missing_source_pdf_safe_degraded(test_db: Session):
    doc = Document(
        title="Missing File Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="doc3.pdf",
        storage_key="doc3.pdf",
        mime_type="application/pdf",
        file_size_bytes=150,
        sha256_checksum="abc3",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
    )
    test_db.add(doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": [], "metadatas": []}

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("os.path.isfile", return_value=False):
        summary = reconcile_index_state(db=test_db, repair=True)
        test_db.refresh(doc)
        assert doc.index_status == IndexStatus.FAILED.value
        assert "Physical source file missing from storage" in doc.index_error
        assert summary["missing_source_count"] == 1

        health = check_document_ir_health(test_db)
        assert health["status"] == "degraded"
        assert health["missing_source_count"] == 1


# =============================================================================
# 4. Inactive/deleted doc vectors are purged
# =============================================================================
def test_4_inactive_and_deleted_doc_vectors_are_purged(test_db: Session):
    inactive_doc = Document(
        title="Inactive Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="inactive.pdf",
        storage_key="inactive.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="inact1",
        is_active=False,
        index_status=IndexStatus.INDEXED.value,
    )
    test_db.add(inactive_doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["vec_inactive_1", "vec_orphan_99"],
        "metadatas": [
            {"document_id": inactive_doc.id},
            {"document_id": 9999},  # non-existent doc in DB
        ],
    }

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("os.path.isfile", return_value=True):
        summary = reconcile_index_state(db=test_db, repair=True)
        test_db.refresh(inactive_doc)
        assert inactive_doc.index_status == IndexStatus.NOT_INDEXED.value
        assert summary["inactive_vectors_removed"] == 1
        assert summary["stale_vectors_purged"] == 1
        mock_collection.delete.assert_any_call(ids=["vec_inactive_1"])
        mock_collection.delete.assert_any_call(ids=["vec_orphan_99"])


# =============================================================================
# 5. Wrong index_version triggers appropriate repair state
# =============================================================================
def test_5_wrong_index_version_triggers_repair(test_db: Session):
    doc = Document(
        title="Stale Version Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="stale.pdf",
        storage_key="stale.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="stale1",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
        index_version="v0_old",
    )
    test_db.add(doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["vec_1"],
        "metadatas": [{"document_id": doc.id}],
    }

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("os.path.isfile", return_value=True), \
         patch("app.services.chroma_service.auto_index_document", return_value=True) as mock_auto_index:
        summary = reconcile_index_state(db=test_db, repair=True)
        assert summary["reindexed_count"] == 1
        mock_auto_index.assert_called_once_with(db=test_db, document_id=doc.id)


# =============================================================================
# 6. Reconciliation is idempotent
# =============================================================================
def test_6_reconciliation_is_idempotent(test_db: Session):
    from datetime import datetime, timezone
    doc = Document(
        title="Healthy Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="healthy.pdf",
        storage_key="healthy.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="healthy1",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
        index_version=settings.DOCUMENT_INDEX_VERSION,
        last_indexed_at=datetime.now(timezone.utc),
    )
    test_db.add(doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["vec_h1"],
        "metadatas": [{"document_id": doc.id}],
    }

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("os.path.isfile", return_value=True):
        # Run 1
        summary1 = reconcile_index_state(db=test_db, repair=True)
        assert summary1["reconciled_count"] == 0
        assert summary1["reindexed_count"] == 0

        # Run 2
        summary2 = reconcile_index_state(db=test_db, repair=True)
        assert summary2["reconciled_count"] == 0
        assert summary2["reindexed_count"] == 0


# =============================================================================
# 7. Demo bootstrap is idempotent
# =============================================================================
def test_7_demo_bootstrap_is_idempotent(test_db: Session):
    s1 = Supplier(supplier_code="S1", name="TechSource Lanka", is_active=True)
    s2 = Supplier(supplier_code="S2", name="Digital Distribution Lanka", is_active=True)
    s3 = Supplier(supplier_code="S3", name="NextGen Supplies", is_active=True)
    test_db.add_all([s1, s2, s3])
    test_db.commit()

    def fake_auto_index(db, document_id):
        d = db.get(Document, document_id)
        if d:
            d.index_status = IndexStatus.INDEXED.value
            d.index_version = settings.DOCUMENT_INDEX_VERSION
            db.commit()
        return True

    mock_col = MagicMock()
    mock_col.get.return_value = {"ids": ["v_dummy"]}
    mock_col.count.return_value = 8

    with patch("scripts.bootstrap_document_ir.generate_procurement_policy"), \
         patch("scripts.bootstrap_document_ir.generate_inventory_replenishment_policy"), \
         patch("scripts.bootstrap_document_ir.generate_techsource_sla"), \
         patch("scripts.bootstrap_document_ir.generate_digital_distribution_sla"), \
         patch("scripts.bootstrap_document_ir.generate_nextgen_sla"), \
         patch("scripts.bootstrap_document_ir.generate_techsource_performance_review"), \
         patch("scripts.bootstrap_document_ir.generate_digital_performance_review"), \
         patch("scripts.bootstrap_document_ir.generate_nextgen_performance_review"), \
         patch("scripts.bootstrap_document_ir.generate_performance_review"), \
         patch("scripts.bootstrap_document_ir.auto_index_document", side_effect=fake_auto_index), \
         patch("app.services.chroma_service.auto_index_document", side_effect=fake_auto_index), \
         patch("scripts.bootstrap_document_ir._get_collection", return_value=mock_col), \
         patch("app.services.chroma_service._get_collection", return_value=mock_col), \
         patch("os.path.isfile", return_value=True), \
         patch("pathlib.Path.read_bytes", return_value=b"%PDF-1.4 dummy"):

        # First run creates the 8 demo docs
        res1 = bootstrap_document_ir(db=test_db)
        assert res1["active_docs"] == 8
        assert len(res1["actions_performed"]) == 8

        # Second run should perform 0 actions
        res2 = bootstrap_document_ir(db=test_db)
        assert len(res2["actions_performed"]) == 0
        assert res2["active_docs"] == 8


# =============================================================================
# 8. Final DecisionRecommendationResponse includes evidence
# =============================================================================
def test_8_final_decision_response_includes_evidence():
    evidence_chunk = DocumentSearchResult(
        document_id=18,
        document_title="TechSource Lanka Service Level Agreement",
        title="TechSource Lanka Service Level Agreement",
        document_type="supplier_sla",
        supplier_id=9,
        page_number=1,
        chunk_index=0,
        text="Deliveries are made within 5 business days.",
        distance=0.12,
        source_type="document_ir",
        authority="policy_or_sla",
    )

    opt = SupplierCandidateOption(
        supplier_id=9,
        supplier_name="TechSource Lanka",
        unit_cost=2400.0,
        moq=30,
        lead_time_days=5,
        advantages=["Compliant with SLA"],
        risks=[],
        evidence=[evidence_chunk],
    )

    response = DecisionRecommendationResponse(
        product_id=1,
        product_name="Test Product",
        replenishment_required=True,
        recommended_order_quantity=50,
        risk_level="LOW",
        reasoning="Optimal supplier meets all criteria.",
        supplier_options=[opt],
    )

    payload = response.model_dump()
    assert "supplier_options" in payload
    assert len(payload["supplier_options"][0]["evidence"]) == 1
    ev_out = payload["supplier_options"][0]["evidence"][0]
    assert ev_out["document_id"] == 18
    assert ev_out["document_title"] == "TechSource Lanka Service Level Agreement"
    assert ev_out["source_type"] == "document_ir"
    assert ev_out["authority"] == "policy_or_sla"


# =============================================================================
# 9. Evidence document IDs/pages/text match SupplierAgent evidence
# =============================================================================
def test_9_evidence_preserves_supplier_agent_values(test_db: Session):
    from app.agents.decision.agent import DecisionAgent

    agent = DecisionAgent()
    p = Product(name="Smart Mouse", sku="SM-01", reorder_point=10, is_active=True)
    s = Supplier(name="TechSource Lanka", supplier_code="TSL-01", is_active=True)
    test_db.add_all([p, s])
    test_db.commit()

    ps = ProductSupplier(product_id=p.id, supplier_id=s.id, unit_cost=Decimal("2000.00"), moq=10, lead_time_days=4, is_active=True)
    test_db.add(ps)
    test_db.commit()

    agent_evidence = [
        DocumentSearchResult(
            document_id=55,
            document_title="TechSource SLA 2026",
            title="TechSource SLA 2026",
            document_type="supplier_sla",
            supplier_id=s.id,
            page_number=3,
            chunk_index=2,
            text="Exact clause excerpt from page 3.",
            distance=0.08,
            source_type="document_ir",
            authority="policy_or_sla",
        )
    ]

    mock_supplier_resp = SupplierAgentResponse(
        candidate_assessments=[
            CandidateAssessment(
                supplier_id=s.id,
                supplier_code=s.supplier_code,
                supplier_name=s.name,
                unit_cost=2000.0,
                moq=10,
                lead_time_days=4,
                evidence=agent_evidence,
            )
        ]
    )

    req = DecisionRecommendationRequest(product_id=p.id, forecast_horizon_days=14)
    with patch("app.agents.supplier_procurement_agent.SupplierProcurementAgent.assess_suppliers", return_value=mock_supplier_resp), \
         patch.object(agent, "_synthesize_explanation_with_grok", return_value=("Reasoning", ["Factor 1"], 0.95)):
        res = agent.generate_recommendation(request=req, db=test_db)
        assert len(res.supplier_options) == 1
        opt = res.supplier_options[0]
        assert len(opt.evidence) == 1
        assert opt.evidence[0].document_id == 55
        assert opt.evidence[0].page_number == 3
        assert opt.evidence[0].chunk_index == 2
        assert opt.evidence[0].text == "Exact clause excerpt from page 3."


# =============================================================================
# 10. No fake citations appear
# =============================================================================
def test_10_no_fake_citations_when_ir_returns_none(test_db: Session):
    from app.agents.decision.agent import DecisionAgent

    agent = DecisionAgent()
    p = Product(name="Basic Cable", sku="BC-01", reorder_point=5, is_active=True)
    s = Supplier(name="Generic Supplier", supplier_code="GEN-01", is_active=True)
    test_db.add_all([p, s])
    test_db.commit()

    ps = ProductSupplier(product_id=p.id, supplier_id=s.id, unit_cost=Decimal("500.00"), moq=1, lead_time_days=2, is_active=True)
    test_db.add(ps)
    test_db.commit()

    # Empty evidence returned by IR
    mock_supplier_resp = SupplierAgentResponse(
        candidate_assessments=[
            CandidateAssessment(
                supplier_id=s.id,
                supplier_code=s.supplier_code,
                supplier_name=s.name,
                unit_cost=500.0,
                moq=1,
                lead_time_days=2,
                evidence=[],
            )
        ]
    )

    req = DecisionRecommendationRequest(product_id=p.id, forecast_horizon_days=14)
    with patch("app.agents.supplier_procurement_agent.SupplierProcurementAgent.assess_suppliers", return_value=mock_supplier_resp), \
         patch.object(agent, "_synthesize_explanation_with_grok", return_value=("Reasoning", ["Factor 1"], 0.95)):
        res = agent.generate_recommendation(request=req, db=test_db)
        assert len(res.supplier_options) == 1
        # Absolutely no fabricated citations
        assert res.supplier_options[0].evidence == []


# =============================================================================
# 11. PostgreSQL commercial values remain unchanged by document evidence
# =============================================================================
def test_11_commercial_values_unchanged_by_document_evidence(test_db: Session):
    from app.agents.decision.agent import DecisionAgent

    agent = DecisionAgent()
    p = Product(name="Hard Drive", sku="HD-01", reorder_point=20, is_active=True)
    s = Supplier(name="TechStore", supplier_code="TS-01", is_active=True)
    test_db.add_all([p, s])
    test_db.commit()

    auth_unit_cost = 15000.0
    auth_moq = 25
    auth_lead_time = 10

    ps = ProductSupplier(
        product_id=p.id,
        supplier_id=s.id,
        unit_cost=Decimal(str(auth_unit_cost)),
        moq=auth_moq,
        lead_time_days=auth_lead_time,
        is_active=True,
    )
    test_db.add(ps)
    test_db.commit()

    # Evidence mentioning contradictory/promotional numbers
    contradictory_evidence = [
        DocumentSearchResult(
            document_id=77,
            document_title="Promotional Flyer",
            title="Promotional Flyer",
            document_type="supplier_contract",
            supplier_id=s.id,
            page_number=1,
            chunk_index=0,
            text="Special discount: Unit cost LKR 5000, MOQ 5, 2 days delivery!",
            source_type="document_ir",
            authority="policy_or_sla",
        )
    ]

    mock_supplier_resp = SupplierAgentResponse(
        candidate_assessments=[
            CandidateAssessment(
                supplier_id=s.id,
                supplier_code=s.supplier_code,
                supplier_name=s.name,
                unit_cost=auth_unit_cost,
                moq=auth_moq,
                lead_time_days=auth_lead_time,
                evidence=contradictory_evidence,
            )
        ]
    )

    req = DecisionRecommendationRequest(product_id=p.id, forecast_horizon_days=14)
    with patch("app.agents.supplier_procurement_agent.SupplierProcurementAgent.assess_suppliers", return_value=mock_supplier_resp), \
         patch.object(agent, "_synthesize_explanation_with_grok", return_value=("Reasoning", ["Factor 1"], 0.95)):
        res = agent.generate_recommendation(request=req, db=test_db)
        opt = res.supplier_options[0]

        # Authoritative commercial values MUST NOT be overwritten
        assert opt.unit_cost == auth_unit_cost
        assert opt.moq == auth_moq
        assert opt.lead_time_days == auth_lead_time


# =============================================================================
# 12. Existing supplier-selection and decision tests pass
# =============================================================================
def test_12_existing_supplier_selection_business_logic():
    from app.services.decision_service import select_best_supplier_candidate

    candidates = [
        {"supplier_id": 1, "supplier_name": "Supplier A", "unit_cost": 2500.0, "moq": 10, "lead_time_days": 7},
        {"supplier_id": 2, "supplier_name": "Supplier B", "unit_cost": 2200.0, "moq": 50, "lead_time_days": 14},
    ]

    # Lowest cost selected under normal urgency
    chosen, qty, _, _ = select_best_supplier_candidate(candidates=candidates, recommended_quantity=60, urgency="normal")
    assert chosen["supplier_id"] == 2
    assert qty == 60

    # Shortest lead time selected under emergency urgency
    chosen_urg, qty_urg, _, _ = select_best_supplier_candidate(candidates=candidates, recommended_quantity=60, urgency="emergency")
    assert chosen_urg["supplier_id"] == 1
    assert qty_urg == 60
