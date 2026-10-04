import io
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import pymupdf
from app.main import app
from app.core.config import settings
from app.database.session import get_db
from app.database.base import Base
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.models.document import Document, DocumentType, IndexStatus
from app.models.supplier import Supplier
from app.schemas.document import DocumentUpdate
from app.services.chroma_service import (
    search_documents,
    index_document_chunks,
    delete_document_vectors,
    is_document_indexed,
    get_document_index_status,
    auto_index_document,
    reconcile_index_state,
    check_document_ir_health,
    sanitize_error_message,
)
from app.services.document_service import (
    create_document,
    update_document,
    delete_document,
    get_document,
)
from app.schemas.document_processing import DocumentChunkResponse


def _generate_test_pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    return doc.tobytes()


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
def mock_admin_user(test_db: Session) -> User:
    user = User(
        email="admin_retrieval@example.com",
        name="Admin Retrieval",
        role=UserRole.ADMIN.value,
        password_hash="fakehashedpassword",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def client(test_db: Session, mock_admin_user: User, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path / "documents"))

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
# 1. RETRIEVAL & VALIDATION TESTS
# =============================================================================

def test_search_documents_validation():
    with pytest.raises(ValueError, match="Query string must be non"):
        search_documents(query="")

    with pytest.raises(ValueError, match="top_k must be between 1 and 20"):
        search_documents(query="valid query", top_k=0)

    with pytest.raises(ValueError, match="top_k must be between 1 and 20"):
        search_documents(query="valid query", top_k=25)


def test_api_search_post_endpoint(client: TestClient):
    mock_hit = {
        "rank": 1,
        "chunk_id": "doc-11-p1-c2",
        "document_id": 11,
        "document_title": "TechSource Lanka Service Level Agreement",
        "document_type": "supplier_sla",
        "supplier_id": 9,
        "page_number": 1,
        "chunk_index": 2,
        "text": "TechSource Lanka commits to maintaining a minimum monthly On-Time Delivery rate of 95.0%.",
        "distance": 0.5930,
    }

    with patch("app.routers.retrieval.search_documents", return_value=[mock_hit]) as mock_search:
        response = client.post(
            "/api/v1/documents/search",
            json={"query": "What happens if TechSource Lanka delivers late?", "top_k": 3},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["chunk_id"] == "doc-11-p1-c2"
        assert data[0]["page_number"] == 1
        assert data[0]["document_type"] == "supplier_sla"
        from unittest.mock import ANY
        mock_search.assert_called_once_with(
            query="What happens if TechSource Lanka delivers late?",
            top_k=3,
            document_type=None,
            supplier_id=None,
            db=ANY,
        )


def test_api_search_get_endpoint(client: TestClient):
    mock_hit = {
        "rank": 1,
        "chunk_id": "doc-9-p1-c2",
        "document_id": 9,
        "document_title": "SmartSupply Procurement Policy 2026",
        "document_type": "procurement_policy",
        "supplier_id": None,
        "page_number": 1,
        "chunk_index": 2,
        "text": "Expenditure Thresholds and Approval Authority.",
        "distance": 0.6977,
    }

    with patch("app.routers.retrieval.search_documents", return_value=[mock_hit]) as mock_search:
        response = client.get(
            "/api/v1/documents/search",
            params={"q": "What approval is required for purchases above LKR 500,000?", "top_k": 5},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["document_type"] == "procurement_policy"
        from unittest.mock import ANY
        mock_search.assert_called_once_with(
            query="What approval is required for purchases above LKR 500,000?",
            top_k=5,
            document_type=None,
            supplier_id=None,
            db=ANY,
        )


def test_api_reindex_endpoints(client: TestClient):
    mock_summary = {"documents_indexed": 6, "chunks_indexed": 45}

    with patch("app.routers.retrieval.rebuild_index", return_value=mock_summary), \
         patch("app.routers.retrieval.list_documents", return_value=[]):
        # Test POST /api/v1/documents/reindex
        response = client.post("/api/v1/documents/reindex")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == mock_summary

        # Test POST /api/v1/documents/reindex-all
        response_all = client.post("/api/v1/documents/reindex-all")
        assert response_all.status_code == status.HTTP_200_OK
        assert response_all.json() == mock_summary


# =============================================================================
# 2. AUTOMATIC INDEXING LIFECYCLE & FAILURE TESTS
# =============================================================================

def test_upload_automatically_indexes(client: TestClient, test_db: Session):
    pdf_bytes = _generate_test_pdf_bytes("Emergency procurement protocol requires managerial approval.")

    with patch("app.services.chroma_service.auto_index_document") as mock_auto_index, \
         patch("app.services.chroma_service.is_document_indexed", return_value=True):
        mock_auto_index.return_value = True

        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Emergency Procurement SOP 2026",
                "document_type": DocumentType.PROCUREMENT_POLICY.value,
            },
            files={
                "file": ("emergency_sop.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Emergency Procurement SOP 2026"
        assert data["indexed"] is True
        mock_auto_index.assert_called_once()
        assert mock_auto_index.call_args[1]["document_id"] == data["id"]


def test_indexing_failure_does_not_lose_valid_uploaded_document(client: TestClient, test_db: Session, tmp_path):
    pdf_bytes = _generate_test_pdf_bytes("Standard procurement procedures and guidelines.")

    # Simulate Chroma/Embedding failure during indexing
    with patch("app.services.chroma_service.auto_index_document", side_effect=RuntimeError("Chroma down")), \
         patch("app.services.chroma_service.is_document_indexed", return_value=False):

        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Robust Upload Policy 2026",
                "document_type": DocumentType.PROCUREMENT_POLICY.value,
            },
            files={
                "file": ("robust_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
            },
        )
        # Upload MUST still succeed despite indexing failure
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Robust Upload Policy 2026"
        assert data["indexed"] is False

        # Verify DB metadata is safely stored
        doc_id = data["id"]
        doc_in_db = get_document(test_db, doc_id)
        assert doc_in_db is not None
        assert doc_in_db.title == "Robust Upload Policy 2026"

        # Verify physical file is safely stored on disk
        storage_dir = str(tmp_path / "documents")
        assert os.path.exists(os.path.join(storage_dir, doc_in_db.storage_key))


def test_delete_removes_vectors(test_db: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path / "documents"))
    os.makedirs(str(tmp_path / "documents"), exist_ok=True)

    pdf_bytes = _generate_test_pdf_bytes("Policy to be deleted.")
    storage_key = "delete_test.pdf"
    file_path = os.path.join(str(tmp_path / "documents"), storage_key)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    doc = Document(
        title="Doc to Delete",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="delete.pdf",
        storage_key=storage_key,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        sha256_checksum="dummy123456",
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)
    doc_id = doc.id

    with patch("app.services.chroma_service.delete_document_vectors") as mock_del_vec:
        delete_document(db=test_db, document_id=doc_id)
        mock_del_vec.assert_called_once_with(document_id=doc_id)

    assert not os.path.exists(file_path)


def test_inactive_document_removes_vectors(test_db: Session):
    doc = Document(
        title="Active Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="active.pdf",
        storage_key="active.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="dummy123456",
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    with patch("app.services.chroma_service.delete_document_vectors") as mock_del_vec:
        update_document(db=test_db, document_id=doc.id, payload=DocumentUpdate(is_active=False))
        mock_del_vec.assert_called_once_with(document_id=doc.id)


def test_reactivation_reindexes_document(test_db: Session):
    doc = Document(
        title="Inactive Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="inactive.pdf",
        storage_key="inactive.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="dummy123456",
        is_active=False,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    with patch("app.services.chroma_service.auto_index_document") as mock_auto_index:
        update_document(db=test_db, document_id=doc.id, payload=DocumentUpdate(is_active=True))
        mock_auto_index.assert_called_once_with(db=test_db, document_id=doc.id)


def test_metadata_update_refreshes_chroma(test_db: Session):
    doc = Document(
        title="Old Title Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="doc.pdf",
        storage_key="doc.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="dummy123456",
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    with patch("app.services.chroma_service.auto_index_document") as mock_auto_index:
        update_document(db=test_db, document_id=doc.id, payload=DocumentUpdate(title="New Title Doc"))
        mock_auto_index.assert_called_once_with(db=test_db, document_id=doc.id)


def test_no_duplicate_vectors_after_repeated_indexing():
    mock_collection = MagicMock()
    # Simulate Chroma collection upsert
    upserted_ids = set()
    def mock_upsert(ids, embeddings, metadatas, documents):
        upserted_ids.update(ids)

    mock_collection.upsert = mock_upsert

    sample_chunks = [
        DocumentChunkResponse(
            chunk_id=f"doc-100-p1-c{i}",
            document_id=100,
            document_title="Sample Doc",
            document_type="procurement_policy",
            supplier_id=None,
            page_number=1,
            start_page=1,
            end_page=1,
            chunk_index=i,
            text=f"Sample text block {i}",
            char_count=20,
        )
        for i in range(3)
    ]

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("app.services.embedding_service.EmbeddingProvider.embed_texts", return_value=[[0.1]*384]*3):
        # Index once
        index_document_chunks(document_id=100, chunks=sample_chunks)
        assert len(upserted_ids) == 3

        # Index again with identical chunks (simulating re-index)
        index_document_chunks(document_id=100, chunks=sample_chunks)
        # Because IDs are deterministic, set length remains strictly 3
        assert len(upserted_ids) == 3


def test_index_status_endpoint(client: TestClient, test_db: Session):
    doc = Document(
        title="Status Test Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="status.pdf",
        storage_key="status.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="dummy123456",
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    mock_status = {
        "document_id": doc.id,
        "indexed": True,
        "chunk_count": 5,
        "error": None,
    }

    with patch("app.routers.retrieval.get_document_index_status", return_value=mock_status):
        response = client.get(f"/api/v1/documents/{doc.id}/index-status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["document_id"] == doc.id
        assert data["indexed"] is True
        assert data["chunk_count"] == 5


# =============================================================================
# 4. PRODUCTION LIFECYCLE & OPERATIONAL TESTS
# =============================================================================

def test_document_upload_lifecycle_success(test_db: Session):
    """Test full upload lifecycle transition to indexed with timestamp and version."""
    doc = Document(
        title="Lifecycle Success Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="policy.pdf",
        storage_key="policy.pdf",
        mime_type="application/pdf",
        file_size_bytes=200,
        sha256_checksum="dummychecksum1",
        is_active=True,
        index_status=IndexStatus.PENDING.value,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    sample_chunks = [
        DocumentChunkResponse(
            chunk_id=f"doc-{doc.id}-p1-c0",
            document_id=doc.id,
            document_title=doc.title,
            document_type=doc.document_type,
            supplier_id=None,
            page_number=1,
            start_page=1,
            end_page=1,
            chunk_index=0,
            text="Lifecycle policy terms.",
            char_count=23,
        )
    ]

    with patch("app.services.document_processing_service.process_document", return_value=MagicMock(chunks=sample_chunks)), \
         patch("app.services.chroma_service.index_document_chunks", return_value=1):
        res = auto_index_document(db=test_db, document_id=doc.id)
        assert res is True

        test_db.refresh(doc)
        assert doc.index_status == IndexStatus.INDEXED.value
        assert doc.last_indexed_at is not None
        assert doc.index_version == settings.DOCUMENT_INDEX_VERSION
        assert doc.index_error is None


def test_document_indexing_failure_state(test_db: Session):
    """Test indexing failure updates status to failed with sanitized error."""
    doc = Document(
        title="Lifecycle Failure Doc",
        document_type=DocumentType.SUPPLIER_CONTRACT.value,
        supplier_id=None,
        original_filename="contract.pdf",
        storage_key="contract.pdf",
        mime_type="application/pdf",
        file_size_bytes=200,
        sha256_checksum="dummychecksum2",
        is_active=True,
        index_status=IndexStatus.PENDING.value,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    with patch("app.services.document_processing_service.process_document", side_effect=ValueError("Corrupt PDF file at C:\\secret\\docs\\contract.pdf")):
        res = auto_index_document(db=test_db, document_id=doc.id)
        assert res is False

        test_db.refresh(doc)
        assert doc.index_status == IndexStatus.FAILED.value
        assert doc.index_error is not None
        assert "C:\\secret\\docs" not in doc.index_error


def test_document_deactivation_and_reactivation_lifecycle(test_db: Session):
    """Test inactive documents become not_indexed and reactivation reindexes them."""
    doc = Document(
        title="Toggle Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="toggle.pdf",
        storage_key="toggle.pdf",
        mime_type="application/pdf",
        file_size_bytes=200,
        sha256_checksum="dummychecksum3",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
        index_version="v1",
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    with patch("app.services.chroma_service.delete_document_vectors") as mock_del:
        # Deactivate
        update_document(db=test_db, document_id=doc.id, payload=DocumentUpdate(is_active=False))
        test_db.refresh(doc)
        assert doc.is_active is False
        assert doc.index_status == IndexStatus.NOT_INDEXED.value
        mock_del.assert_called_once_with(document_id=doc.id)

    with patch("app.services.chroma_service.auto_index_document") as mock_auto_index:
        # Reactivate
        update_document(db=test_db, document_id=doc.id, payload=DocumentUpdate(is_active=True))
        test_db.refresh(doc)
        assert doc.is_active is True
        mock_auto_index.assert_called_once_with(db=test_db, document_id=doc.id)


def test_index_consistency_db_indexed_but_chroma_zero_vectors_reports_degraded(test_db: Session):
    """If DB says indexed but Chroma returns zero vectors, return degraded/not_indexed."""
    doc = Document(
        title="Desync Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="desync.pdf",
        storage_key="desync.pdf",
        mime_type="application/pdf",
        file_size_bytes=200,
        sha256_checksum="dummychecksum4",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": []}

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection):
        status_res = get_document_index_status(document_id=doc.id, db=test_db)
        assert status_res["indexed"] is False
        assert status_res["index_status"] == IndexStatus.NOT_INDEXED.value
        assert "missing" in status_res["error"].lower() or "degraded" in status_res["error"].lower()


def test_reconciliation_repairs_lifecycle_states(test_db: Session):
    """Test maintenance reconciliation function corrects inconsistent document states."""
    # Doc 1: Active, pending in DB, but has 2 vectors in Chroma -> should become indexed
    d1 = Document(
        title="Doc 1",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="d1.pdf",
        storage_key="d1.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="c1",
        is_active=True,
        index_status=IndexStatus.PENDING.value,
    )
    # Doc 2: Active, indexed in DB, but 0 vectors in Chroma -> should become not_indexed
    d2 = Document(
        title="Doc 2",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="d2.pdf",
        storage_key="d2.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="c2",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
    )
    # Doc 3: Inactive, indexed in DB, has vectors in Chroma -> purge vectors, should become not_indexed
    d3 = Document(
        title="Doc 3",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="d3.pdf",
        storage_key="d3.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="c3",
        is_active=False,
        index_status=IndexStatus.INDEXED.value,
    )
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["c1_0", "c1_1", "c3_0"],
        "metadatas": [
            {"document_id": d1.id},
            {"document_id": d1.id},
            {"document_id": d3.id},
        ]
    }

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("os.path.isfile", return_value=True):
        summary = reconcile_index_state(test_db, repair=False)

        test_db.refresh(d1)
        test_db.refresh(d2)
        test_db.refresh(d3)

        assert d1.index_status == IndexStatus.INDEXED.value
        assert d2.index_status == IndexStatus.NOT_INDEXED.value
        assert d3.index_status == IndexStatus.NOT_INDEXED.value

        mock_collection.delete.assert_called_with(ids=["c3_0"])
        assert summary["total_documents_checked"] == 3
        assert summary["reconciled_count"] == 3


def test_document_ir_health_endpoint_healthy(client: TestClient, test_db: Session):
    """Test health endpoint reports healthy with valid stats."""
    doc = Document(
        title="Health Doc",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="health.pdf",
        storage_key="health.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        sha256_checksum="c_health",
        is_active=True,
        index_status=IndexStatus.INDEXED.value,
    )
    test_db.add(doc)
    test_db.commit()

    mock_collection = MagicMock()
    mock_collection.count.return_value = 8

    with patch("app.services.chroma_service._get_collection", return_value=mock_collection), \
         patch("app.services.embedding_service.EmbeddingProvider.embed_texts", return_value=[[0.1] * 384]), \
         patch("os.path.isfile", return_value=True):
        response = client.get("/api/v1/health/document-ir")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["postgres_connected"] is True
        assert data["chroma_available"] is True
        assert data["embedding_available"] is True
        assert data["active_document_count"] == 1
        assert data["indexed_document_count"] == 1
        assert data["failed_document_count"] == 0
        assert data["vector_count"] == 8
        assert data["index_version"] == settings.DOCUMENT_INDEX_VERSION


def test_document_ir_health_endpoint_degraded_when_chroma_fails(client: TestClient, test_db: Session):
    """Test health endpoint reports degraded without crashing when Chroma is unreachable."""
    with patch("app.services.chroma_service._get_collection", side_effect=RuntimeError("Chroma DB failed at C:\\storage\\chroma")), \
         patch("app.services.embedding_service.EmbeddingProvider.embed_texts", return_value=[[0.1] * 384]):
        response = client.get("/api/v1/health/document-ir")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "degraded"
        assert data["chroma_available"] is False
        assert "C:\\storage\\chroma" not in str(data["details"])


def test_sanitize_error_message_masks_secrets_and_paths():
    """Verify secrets and paths are masked safely."""
    raw = "Failed connection to postgresql://user:my_secret_pass@127.0.0.1:5432/smartsupply_db file C:\\irwa project\\backend\\storage\\test.pdf"
    cleaned = sanitize_error_message(raw)
    assert "my_secret_pass" not in cleaned
    assert "C:\\irwa project" not in cleaned
    assert "[REDACTED" in cleaned


