import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import patch, MagicMock
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
from app.models.document import Document, DocumentType
from app.services.query_understanding_service import (
    analyze_query,
    resolve_supplier_entity,
    resolve_product_entity,
    INTENT_SUPPLIER_TERMS,
    INTENT_SUPPLIER_POLICY,
    INTENT_PROCUREMENT_POLICY,
    INTENT_INVENTORY_POLICY,
    INTENT_SUPPLIER_LOOKUP,
    INTENT_SUPPLIER_COMPARISON,
    INTENT_MIXED_DECISION,
    INTENT_UNKNOWN,
    ROUTE_STRUCTURED,
    ROUTE_DOCUMENT,
    ROUTE_MIXED,
    ROUTE_UNKNOWN,
)
from app.services.supplier_knowledge_service import (
    get_supplier,
    get_product,
    get_product_supplier_offers,
    get_supplier_offer,
    get_suppliers_for_product,
    search_supplier_documents,
    search_procurement_policy,
    search_inventory_policy,
    resolve_supplier_knowledge,
)
from app.services.chroma_service import search_documents


# =============================================================================
# FIXTURES
# =============================================================================

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
def mock_admin(test_db: Session) -> User:
    user = User(
        email="sk_admin@example.com",
        name="SK Admin",
        role=UserRole.ADMIN.value,
        password_hash="fakehash",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def seed_data(test_db: Session):
    s1 = Supplier(
        supplier_code="DEMO-SUP-001",
        name="TechSource Lanka",
        contact_name="Kamal Silva",
        email="kamal@techsource.lk",
        phone="+94 11 234 5678",
        address="100 Galle Road, Colombo",
        is_active=True,
    )
    s2 = Supplier(
        supplier_code="DEMO-SUP-002",
        name="Digital Distribution Lanka",
        contact_name="Ruwan Perera",
        email="ruwan@digitaldist.lk",
        phone="+94 11 345 6789",
        address="200 Kandy Road, Kelaniya",
        is_active=True,
    )
    s3_inactive = Supplier(
        supplier_code="INACTIVE-SUP-001",
        name="Old Inactive Tech",
        contact_name="Old Contact",
        email="old@old.lk",
        phone="+94 11 000 0000",
        address="Old Street",
        is_active=False,
    )
    test_db.add_all([s1, s2, s3_inactive])
    test_db.commit()

    p1 = Product(
        sku="DEMO-001",
        name="Wireless Mouse",
        category="Peripherals",
        description="Ergonomic 2.4GHz wireless optical mouse",
        unit_price=Decimal("3200.00"),
        reorder_point=25,
        is_active=True,
    )
    p2 = Product(
        sku="DEMO-002",
        name="Mechanical Keyboard",
        category="Peripherals",
        description="RGB backlit mechanical gaming keyboard",
        unit_price=Decimal("11500.00"),
        reorder_point=15,
        is_active=True,
    )
    test_db.add_all([p1, p2])
    test_db.commit()

    # Commercial offers
    ps1 = ProductSupplier(
        product_id=p1.id,
        supplier_id=s1.id,
        supplier_sku="TS-WM-01",
        unit_cost=Decimal("2400.00"),
        moq=30,
        lead_time_days=5,
        is_active=True,
    )
    ps2 = ProductSupplier(
        product_id=p1.id,
        supplier_id=s2.id,
        supplier_sku="DD-WM-01",
        unit_cost=Decimal("2550.00"),
        moq=20,
        lead_time_days=2,
        is_active=True,
    )
    ps3_inactive = ProductSupplier(
        product_id=p2.id,
        supplier_id=s1.id,
        supplier_sku="TS-KB-INACTIVE",
        unit_cost=Decimal("8000.00"),
        moq=50,
        lead_time_days=10,
        is_active=False,
    )
    test_db.add_all([ps1, ps2, ps3_inactive])
    test_db.commit()

    # Add active and inactive Document records in DB
    d1 = Document(
        title="TechSource Lanka Service Level Agreement",
        document_type=DocumentType.SUPPLIER_SLA.value,
        supplier_id=s1.id,
        original_filename="techsource_sla.pdf",
        storage_key="techsource_sla.pdf",
        mime_type="application/pdf",
        file_size_bytes=5000,
        sha256_checksum="hash_d1",
        is_active=True,
    )
    d2_inactive = Document(
        title="Deactivated Outdated Policy",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="outdated.pdf",
        storage_key="outdated.pdf",
        mime_type="application/pdf",
        file_size_bytes=3000,
        sha256_checksum="hash_d2",
        is_active=False,
    )
    test_db.add_all([d1, d2_inactive])
    test_db.commit()

    return {
        "s1": s1,
        "s2": s2,
        "s3_inactive": s3_inactive,
        "p1": p1,
        "p2": p2,
        "d1": d1,
        "d2_inactive": d2_inactive,
    }


@pytest.fixture
def client(test_db: Session, mock_admin: User):
    def override_get_db():
        yield test_db

    def override_get_current_user():
        return mock_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# =============================================================================
# 1. QUERY UNDERSTANDING & ENTITY RESOLUTION TESTS
# =============================================================================

def test_entity_resolution_supplier_name(test_db: Session, seed_data):
    # Matches brand name "TechSource" to "TechSource Lanka"
    supp = resolve_supplier_entity("What is TechSource lead time?", test_db)
    assert supp is not None
    assert supp.name == "TechSource Lanka"

    # Matches full name "Digital Distribution Lanka"
    supp2 = resolve_supplier_entity("Check Digital Distribution Lanka SLA", test_db)
    assert supp2 is not None
    assert supp2.name == "Digital Distribution Lanka"


def test_entity_resolution_supplier_code(test_db: Session, seed_data):
    supp = resolve_supplier_entity("Inquire with DEMO-SUP-001 regarding restocking", test_db)
    assert supp is not None
    assert supp.supplier_code == "DEMO-SUP-001"
    assert supp.name == "TechSource Lanka"


def test_entity_resolution_product_sku(test_db: Session, seed_data):
    prod = resolve_product_entity("What is the price of DEMO-001?", test_db)
    assert prod is not None
    assert prod.sku == "DEMO-001"
    assert prod.name == "Wireless Mouse"


def test_entity_resolution_product_name(test_db: Session, seed_data):
    prod = resolve_product_entity("Who supplies the wireless mouse?", test_db)
    assert prod is not None
    assert prod.sku == "DEMO-001"

    # Plural alias
    prod_alias = resolve_product_entity("Check inventory of wireless mice", test_db)
    assert prod_alias is not None
    assert prod_alias.sku == "DEMO-001"


def test_intent_and_route_structured_supplier_terms(test_db: Session, seed_data):
    analysis = analyze_query("What is TechSource MOQ and lead time for the wireless mouse?", test_db)
    assert analysis.intent == INTENT_SUPPLIER_TERMS
    assert analysis.route == ROUTE_STRUCTURED
    assert analysis.supplier_name == "TechSource Lanka"
    assert analysis.sku == "DEMO-001"
    assert analysis.confidence >= 0.90


def test_intent_and_route_structured_supplier_lookup(test_db: Session, seed_data):
    analysis = analyze_query("Which suppliers provide DEMO-001?", test_db)
    assert analysis.intent == INTENT_SUPPLIER_LOOKUP
    assert analysis.route == ROUTE_STRUCTURED
    assert analysis.sku == "DEMO-001"


def test_intent_and_route_document_supplier_policy(test_db: Session, seed_data):
    analysis = analyze_query("What happens if TechSource Lanka delivers late?", test_db)
    assert analysis.intent == INTENT_SUPPLIER_POLICY
    assert analysis.route == ROUTE_DOCUMENT
    assert analysis.supplier_name == "TechSource Lanka"


def test_intent_and_route_document_procurement_policy(test_db: Session, seed_data):
    analysis = analyze_query("What approval is required for purchases above LKR 500,000?", test_db)
    assert analysis.intent == INTENT_PROCUREMENT_POLICY
    assert analysis.route == ROUTE_DOCUMENT


def test_intent_and_route_document_inventory_policy(test_db: Session, seed_data):
    analysis = analyze_query("How should high stockout risk affect replenishment?", test_db)
    assert analysis.intent == INTENT_INVENTORY_POLICY
    assert analysis.route == ROUTE_DOCUMENT


def test_intent_and_route_mixed_decision(test_db: Session, seed_data):
    analysis = analyze_query("Compare supplier information for an emergency wireless mouse order.", test_db)
    assert analysis.intent == INTENT_MIXED_DECISION
    assert analysis.route == ROUTE_MIXED
    assert analysis.sku == "DEMO-001"


def test_intent_unknown_query(test_db: Session, seed_data):
    analysis = analyze_query("Random conversational text unrelated to business", test_db)
    assert analysis.intent == INTENT_UNKNOWN
    assert analysis.route == ROUTE_UNKNOWN
    assert analysis.confidence <= 0.5


# =============================================================================
# 2. STRUCTURED SUPPLIER KNOWLEDGE FUNCTIONS
# =============================================================================

def test_get_product_supplier_offers(test_db: Session, seed_data):
    p1 = seed_data["p1"]
    offers = get_product_supplier_offers(test_db, p1.id, is_active=True)
    assert len(offers) == 2
    # Sorted by unit_cost asc
    assert offers[0]["supplier_name"] == "TechSource Lanka"
    assert offers[0]["unit_cost"] == 2400.00
    assert offers[0]["moq"] == 30
    assert offers[1]["supplier_name"] == "Digital Distribution Lanka"
    assert offers[1]["unit_cost"] == 2550.00


def test_get_supplier_offer(test_db: Session, seed_data):
    p1 = seed_data["p1"]
    s1 = seed_data["s1"]
    offer = get_supplier_offer(test_db, p1.id, s1.id)
    assert offer is not None
    assert offer["unit_cost"] == 2400.00
    assert offer["moq"] == 30
    assert offer["lead_time_days"] == 5


def test_inactive_offers_filtered_by_default(test_db: Session, seed_data):
    p2 = seed_data["p2"]
    offers_active = get_product_supplier_offers(test_db, p2.id, is_active=True)
    assert len(offers_active) == 0

    offers_all = get_product_supplier_offers(test_db, p2.id, is_active=None)
    assert len(offers_all) == 1
    assert offers_all[0]["is_active"] is False


def test_get_suppliers_for_product(test_db: Session, seed_data):
    p1 = seed_data["p1"]
    suppliers = get_suppliers_for_product(test_db, p1.id)
    assert len(suppliers) == 2
    supp_names = [s["supplier_name"] for s in suppliers]
    assert "TechSource Lanka" in supp_names
    assert "Digital Distribution Lanka" in supp_names


# =============================================================================
# 3. PRODUCTION RETRIEVAL SAFETY & STALE VECTOR PROTECTION
# =============================================================================

def test_stale_vector_protection_purges_and_discards(test_db: Session, seed_data):
    """
    Simulates Chroma returning a chunk for a document that was deleted from DB (ID 999)
    and a chunk for an inactive document (d2_inactive).
    search_documents must discard both and only return the active document (d1).
    """
    d1 = seed_data["d1"]
    d2 = seed_data["d2_inactive"]

    mock_collection = MagicMock()
    # Mock Chroma returning 3 chunks
    mock_collection.query.return_value = {
        "ids": [["c-stale-999", f"c-inactive-{d2.id}", f"c-active-{d1.id}"]],
        "metadatas": [[
            {"document_id": 999, "document_title": "Deleted Doc", "document_type": "supplier_sla", "page_number": 1, "chunk_index": 0},
            {"document_id": d2.id, "document_title": d2.title, "document_type": d2.document_type, "page_number": 1, "chunk_index": 0},
            {"document_id": d1.id, "document_title": d1.title, "document_type": d1.document_type, "page_number": 1, "chunk_index": 0},
        ]],
        "documents": [["Stale text", "Inactive text", "Active valid SLA text"]],
        "distances": [[0.3, 0.4, 0.5]],
    }

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("app.services.chroma_service.delete_document_vectors") as mock_delete_vec, \
         patch("app.services.embedding_service.EmbeddingProvider.embed_texts", return_value=[[0.1]*384]):

        hits = search_documents(query="Late delivery penalties", top_k=5, db=test_db)

        # Only the active document (d1) must survive
        assert len(hits) == 1
        assert hits[0]["document_id"] == d1.id
        assert hits[0]["document_title"] == "TechSource Lanka Service Level Agreement"
        assert hits[0]["rank"] == 1

        # Both the non-existent doc (999) and the inactive doc (d2.id) must be targeted for cleanup
        cleaned_ids = [call.kwargs.get("document_id") or call.args[0] for call in mock_delete_vec.call_args_list]
        assert 999 in cleaned_ids
        assert d2.id in cleaned_ids


# =============================================================================
# 4. UNIFIED KNOWLEDGE FUNCTION & ROUTING TESTS
# =============================================================================

def test_resolve_supplier_knowledge_structured(test_db: Session, seed_data):
    res = resolve_supplier_knowledge("What is TechSource MOQ for wireless mouse?", test_db)
    assert res["query_analysis"]["route"] == ROUTE_STRUCTURED
    assert res["query_analysis"]["intent"] == INTENT_SUPPLIER_TERMS
    assert len(res["structured_facts"]) >= 1
    assert res["structured_facts"][0]["moq"] == 30
    assert res["structured_facts"][0]["unit_cost"] == 2400.00
    assert len(res["document_evidence"]) == 0


def test_resolve_supplier_knowledge_document(test_db: Session, seed_data):
    mock_evidence = [{
        "rank": 1,
        "chunk_id": "c-active-1",
        "document_id": seed_data["d1"].id,
        "document_title": "TechSource Lanka Service Level Agreement",
        "document_type": "supplier_sla",
        "supplier_id": seed_data["s1"].id,
        "page_number": 1,
        "chunk_index": 0,
        "text": "1.5% penalty per week for late delivery.",
        "distance": 0.55,
    }]

    with patch("app.services.supplier_knowledge_service.search_supplier_documents", return_value=mock_evidence):
        res = resolve_supplier_knowledge("What happens if TechSource Lanka delivers late?", test_db)
        assert res["query_analysis"]["route"] == ROUTE_DOCUMENT
        assert res["query_analysis"]["intent"] == INTENT_SUPPLIER_POLICY
        assert len(res["structured_facts"]) == 0
        assert len(res["document_evidence"]) == 1
        assert res["document_evidence"][0]["document_title"] == "TechSource Lanka Service Level Agreement"


def test_resolve_supplier_knowledge_mixed(test_db: Session, seed_data):
    mock_evidence = [{
        "rank": 1,
        "chunk_id": "c-policy-1",
        "document_id": 9,
        "document_title": "SmartSupply Procurement Policy 2026",
        "document_type": "procurement_policy",
        "supplier_id": None,
        "page_number": 1,
        "chunk_index": 2,
        "text": "Emergency procurement authorizes fast-lead suppliers.",
        "distance": 0.65,
    }]

    with patch("app.services.supplier_knowledge_service.search_documents", return_value=mock_evidence):
        res = resolve_supplier_knowledge("Compare supplier information for an emergency wireless mouse order.", test_db)
        assert res["query_analysis"]["route"] == ROUTE_MIXED
        assert res["query_analysis"]["intent"] == INTENT_MIXED_DECISION
        # Both structured offers AND document evidence are populated
        assert len(res["structured_facts"]) == 2  # TechSource and Digital Distribution offers
        assert len(res["document_evidence"]) == 1


# =============================================================================
# 5. REST ENDPOINT TEST (POST /api/v1/supplier-knowledge/query)
# =============================================================================

def test_api_supplier_knowledge_query_endpoint(client: TestClient, test_db: Session, seed_data):
    response = client.post(
        "/api/v1/supplier-knowledge/query",
        json={"query": "What is TechSource lead time for wireless mouse?", "top_k": 3},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "query_analysis" in data
    assert data["query_analysis"]["intent"] == INTENT_SUPPLIER_TERMS
    assert data["query_analysis"]["route"] == ROUTE_STRUCTURED
    assert len(data["structured_facts"]) == 1
    assert data["structured_facts"][0]["lead_time_days"] == 5
    assert data["structured_facts"][0]["source_type"] == "postgresql"
    assert data["structured_facts"][0]["authority"] == "operational"
    assert data["needs_clarification"] is False


def test_resolve_supplier_knowledge_unknown_safety(test_db: Session, seed_data):
    """
    Verifies that unknown/unclear queries do NOT run unrestricted fallback search,
    and return needs_clarification=True with a deterministic explanation.
    """
    with patch("app.services.supplier_knowledge_service.search_documents") as mock_search:
        res = resolve_supplier_knowledge("Tell me something about operations.", test_db)
        assert res["query_analysis"]["route"] == ROUTE_UNKNOWN
        assert res["query_analysis"]["intent"] == INTENT_UNKNOWN
        assert res["needs_clarification"] is True
        assert "Could not determine" in res["clarification_reason"]
        assert len(res["structured_facts"]) == 0
        assert len(res["document_evidence"]) == 0
        # Critical safety guarantee: no unrestricted document retrieval was executed
        mock_search.assert_not_called()


def test_api_supplier_knowledge_unknown_query(client: TestClient, test_db: Session, seed_data):
    """
    Validates API response contract for unknown queries requiring clarification.
    """
    response = client.post(
        "/api/v1/supplier-knowledge/query",
        json={"query": "Tell me something about operations."},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["query_analysis"]["route"] == ROUTE_UNKNOWN
    assert data["needs_clarification"] is True
    assert data["clarification_reason"] is not None
    assert data["structured_facts"] == []
    assert data["document_evidence"] == []


def test_source_authority_metadata_labels(test_db: Session, seed_data):
    """
    Verifies that operational structured facts and document IR evidence have distinct authority markers.
    """
    mock_chunk = [{
        "rank": 1,
        "chunk_id": "c-1",
        "document_id": seed_data["d1"].id,
        "document_title": "TechSource Lanka Service Level Agreement",
        "document_type": "supplier_sla",
        "supplier_id": seed_data["s1"].id,
        "page_number": 1,
        "chunk_index": 0,
        "text": "SLA governs service obligations and exceptions.",
        "distance": 0.42,
        "source_type": "document_ir",
        "authority": "policy_or_sla",
    }]
    with patch("app.services.supplier_knowledge_service.search_documents", return_value=mock_chunk):
        res = resolve_supplier_knowledge("Compare supplier information for an emergency wireless mouse order.", test_db)
        # Check structured operational facts
        for f in res["structured_facts"]:
            assert f["source_type"] == "postgresql"
            assert f["authority"] == "operational"

        # Check document evidence
        for d in res["document_evidence"]:
            assert d["source_type"] == "document_ir"
            assert d["authority"] == "policy_or_sla"

