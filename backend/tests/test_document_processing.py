"""
Tests for Document Processing Service:
- PDF text extraction with PyMuPDF
- Conservative text normalization
- Deterministic paragraph-aware chunking
- Provenance and metadata preservation
- Robust error handling (corrupt, empty, missing files)
- Authenticated debug API endpoints
"""

import io
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.database.base import Base
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.document import Document, DocumentType
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.schemas.document_processing import (
    PageExtractionResult,
    DocumentExtractionResponse,
    DocumentChunkResponse,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentStorageError,
    get_storage_dir,
)
from app.services.document_processing_service import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    CorruptedPDFError,
    EncryptedPDFError,
    normalize_text,
    extract_text_from_pdf_bytes,
    chunk_document_text,
    extract_document_text,
    process_document,
)


def _generate_test_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to create a multi-page PDF in memory using ReportLab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in pages_text:
        text_obj = c.beginText(54, 750)
        text_obj.setFont("Helvetica", 10)
        text_obj.setLeading(14)
        for line in text.split("\n"):
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.showPage()
    c.save()
    return buf.getvalue()


# =============================================================================
# 1. TEXT NORMALIZATION TESTS
# =============================================================================
def test_normalize_text_whitespace_and_newlines():
    raw = "  Clause 1.0:   Scope  \r\n\r\n   Section  text with   spaces.\t\t\r\n\n\n\nNext paragraph.  "
    normalized = normalize_text(raw)
    assert normalized.startswith("Clause 1.0: Scope")
    assert "Section text with spaces." in normalized
    # Multiple newlines collapsed to 2
    assert "\n\n" in normalized
    assert "\n\n\n" not in normalized
    assert normalized.endswith("Next paragraph.")


def test_normalize_text_preserves_special_characters_and_words():
    raw = "Supplier SLA: TechSource Lanka (LKR 2,400.00 / unit) — OTIF >= 95.0% & non-breaking\xa0space."
    normalized = normalize_text(raw)
    assert "TechSource Lanka" in normalized
    assert "LKR 2,400.00 / unit" in normalized
    assert "OTIF >= 95.0%" in normalized
    assert "\xa0" not in normalized
    assert "non-breaking space." in normalized


def test_normalize_empty_and_none():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""
    assert normalize_text("   \n\n \t  ") == ""


# =============================================================================
# 2. PDF EXTRACTION TESTS
# =============================================================================
def test_extract_text_valid_multi_page_pdf():
    p1 = "Page 1 Content\nSmartSupply Procurement Policy 2026\nApproved Supplier Requirements."
    p2 = "Page 2 Content\nPurchase Approval Thresholds\nTier 1 up to LKR 100,000."
    pdf_bytes = _generate_test_pdf_bytes([p1, p2])

    pages = extract_text_from_pdf_bytes(pdf_bytes, document_id=101)
    assert len(pages) == 2

    # Check 1-based page numbers
    assert pages[0].page_number == 1
    assert pages[0].document_id == 101
    assert "SmartSupply Procurement Policy" in pages[0].extracted_text
    assert pages[0].char_count > 0

    assert pages[1].page_number == 2
    assert pages[1].document_id == 101
    assert "Purchase Approval Thresholds" in pages[1].extracted_text
    assert pages[1].char_count > 0


def test_extract_text_empty_page_handling():
    p1 = "Page 1 has active text."
    p2 = ""  # blank page
    pdf_bytes = _generate_test_pdf_bytes([p1, p2])

    pages = extract_text_from_pdf_bytes(pdf_bytes, document_id=102)
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert len(pages[0].extracted_text) > 0

    assert pages[1].page_number == 2
    assert pages[1].extracted_text == ""
    assert pages[1].char_count == 0


def test_extract_text_corrupt_pdf():
    corrupt_bytes = b"NOT_A_VALID_PDF_HEADER_OR_BODY_DATA"
    with pytest.raises(CorruptedPDFError):
        extract_text_from_pdf_bytes(corrupt_bytes, document_id=999)


def test_extract_text_empty_bytes():
    with pytest.raises(CorruptedPDFError):
        extract_text_from_pdf_bytes(b"", document_id=999)


# =============================================================================
# 3. CHUNKING & PROVENANCE TESTS
# =============================================================================
def test_deterministic_chunk_output():
    extraction = DocumentExtractionResponse(
        document_id=42,
        document_title="Inventory Replenishment Policy 2026",
        document_type="inventory_replenishment_policy",
        supplier_id=None,
        total_pages=2,
        total_char_count=500,
        pages=[
            PageExtractionResult(
                document_id=42,
                page_number=1,
                extracted_text="Section 1.0 Scope\n\nSection 2.0 Reorder Point calculation.\nROP = Demand * LeadTime + SafetyStock.",
                char_count=95,
            ),
            PageExtractionResult(
                document_id=42,
                page_number=2,
                extracted_text="Section 3.0 Emergency Replenishment.\nFast delivery prioritization applies when stockout risk is critical.",
                char_count=105,
            ),
        ],
    )

    chunks_run1 = chunk_document_text(extraction, chunk_size=800, overlap=100)
    chunks_run2 = chunk_document_text(extraction, chunk_size=800, overlap=100)

    # Must be 100% deterministic
    assert len(chunks_run1) == len(chunks_run2)
    for c1, c2 in zip(chunks_run1, chunks_run2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.chunk_index == c2.chunk_index
        assert c1.page_number == c2.page_number
        assert c1.text == c2.text
        assert c1.char_count == c2.char_count


def test_chunk_metadata_completeness_and_provenance():
    extraction = DocumentExtractionResponse(
        document_id=15,
        document_title="TechSource Lanka SLA",
        document_type="supplier_sla",
        supplier_id=9,
        total_pages=1,
        total_char_count=120,
        pages=[
            PageExtractionResult(
                document_id=15,
                page_number=1,
                extracted_text="Clause 1.0 Terms and conditions of supply.\n\nClause 2.0 Lead time is 5 business days.",
                char_count=85,
            )
        ],
    )

    chunks = chunk_document_text(extraction, chunk_size=500, overlap=50)
    assert len(chunks) >= 1
    c = chunks[0]
    assert c.document_id == 15
    assert c.document_title == "TechSource Lanka SLA"
    assert c.document_type == "supplier_sla"
    assert c.supplier_id == 9
    assert c.page_number == 1
    assert c.start_page == 1
    assert c.end_page == 1
    assert c.chunk_index == 0
    assert len(c.text) > 0
    assert c.char_count == len(c.text)


def test_chunk_overlap_behavior():
    # Long text with multiple distinct paragraphs
    para1 = "Paragraph 1: " + ("Alpha bravo charlie delta echo. " * 15)  # ~450 chars
    para2 = "Paragraph 2: " + ("Foxtrot golf hotel india juliet. " * 15)  # ~450 chars
    para3 = "Paragraph 3: " + ("Kilo lima mike november oscar. " * 15)   # ~450 chars

    full_text = f"{para1}\n\n{para2}\n\n{para3}"

    extraction = DocumentExtractionResponse(
        document_id=77,
        document_title="Overlap Test Document",
        document_type="procurement_policy",
        supplier_id=None,
        total_pages=1,
        total_char_count=len(full_text),
        pages=[
            PageExtractionResult(
                document_id=77,
                page_number=1,
                extracted_text=full_text,
                char_count=len(full_text),
            )
        ],
    )

    chunks = chunk_document_text(extraction, chunk_size=600, overlap=150)
    assert len(chunks) > 1

    # Verify consecutive chunks have overlapping text content
    for i in range(len(chunks) - 1):
        c_curr = chunks[i]
        c_next = chunks[i + 1]
        # At least a segment of the end of current chunk should be in the start of next chunk
        words_curr = c_curr.text.split()[-5:]
        assert any(w in c_next.text for w in words_curr)


def test_chunk_size_limits_not_exceeded():
    # Test with paragraph that splits into multiple chunks
    paragraphs = [f"Paragraph {i}: " + ("Standard regulatory clause testing content. " * 10) for i in range(8)]
    full_text = "\n\n".join(paragraphs)

    extraction = DocumentExtractionResponse(
        document_id=88,
        document_title="Size Limit Test",
        document_type="procurement_policy",
        supplier_id=None,
        total_pages=1,
        total_char_count=len(full_text),
        pages=[
            PageExtractionResult(
                document_id=88,
                page_number=1,
                extracted_text=full_text,
                char_count=len(full_text),
            )
        ],
    )

    chunk_size = 500
    overlap = 100
    chunks = chunk_document_text(extraction, chunk_size=chunk_size, overlap=overlap)
    assert len(chunks) >= 4
    for c in chunks:
        # Paragraph-aware chunking respects chunk_size except for a single unbreakable element
        assert c.char_count <= chunk_size + 50


def test_invalid_chunk_parameters():
    extraction = DocumentExtractionResponse(
        document_id=1,
        document_title="Test",
        document_type="other",
        total_pages=1,
        total_char_count=10,
        pages=[PageExtractionResult(document_id=1, page_number=1, extracted_text="test", char_count=4)],
    )

    with pytest.raises(ValueError, match="chunk_size must be positive"):
        chunk_document_text(extraction, chunk_size=0, overlap=10)

    with pytest.raises(ValueError, match="overlap must be non-negative"):
        chunk_document_text(extraction, chunk_size=500, overlap=-5)

    with pytest.raises(ValueError, match="strictly less than chunk_size"):
        chunk_document_text(extraction, chunk_size=500, overlap=500)


# =============================================================================
# 4. DATABASE & API INTEGRATION FIXTURES & TESTS
# =============================================================================
@pytest.fixture
def test_db():
    """Isolated in-memory SQLite database for testing."""
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
def mock_user(test_db: Session) -> User:
    user = User(
        email="proc_tester@example.com",
        name="Proc Tester",
        role=UserRole.ADMIN.value,
        password_hash="fakehashedpassword",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_pdf_document(test_db: Session, tmp_path, monkeypatch) -> Document:
    monkeypatch.setattr("app.services.document_service.settings.DOCUMENT_STORAGE_DIR", str(tmp_path))

    pdf_content = _generate_test_pdf_bytes([
        "Page 1: SmartSupply Electronics Procurement Policy.\nApproved vendor onboarding.",
        "Page 2: SLA Escalation and Late Delivery Penalties.\nRebate of 1.5% applies.",
    ])

    storage_key = "test_doc_proc.pdf"
    file_path = tmp_path / storage_key
    file_path.write_bytes(pdf_content)

    doc = Document(
        title="Sample Proc Policy",
        document_type=DocumentType.PROCUREMENT_POLICY.value,
        supplier_id=None,
        original_filename="sample_policy.pdf",
        storage_key=storage_key,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_content),
        sha256_checksum="dummy_checksum_12345",
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)
    return doc


def test_extract_and_process_document_service(test_db: Session, sample_pdf_document: Document):
    # Test extract_document_text
    extraction = extract_document_text(test_db, sample_pdf_document.id)
    assert extraction.document_id == sample_pdf_document.id
    assert extraction.total_pages == 2
    assert "SmartSupply Electronics" in extraction.pages[0].extracted_text
    assert "Late Delivery Penalties" in extraction.pages[1].extracted_text

    # Test process_document
    result = process_document(test_db, sample_pdf_document.id, chunk_size=500, overlap=50)
    assert result.document_id == sample_pdf_document.id
    assert result.total_chunks >= 2
    assert result.chunks[0].page_number == 1
    assert result.chunks[1].page_number == 2


def test_extract_missing_file_on_disk(test_db: Session, sample_pdf_document: Document, tmp_path):
    # Remove physical file
    target_file = tmp_path / sample_pdf_document.storage_key
    if target_file.exists():
        target_file.unlink()

    with pytest.raises(DocumentNotFoundError):
        extract_document_text(test_db, sample_pdf_document.id)


def test_api_extracted_text_endpoint(test_db: Session, mock_user: User, sample_pdf_document: Document):
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    try:
        res = client.get(f"/api/v1/documents/{sample_pdf_document.id}/extracted-text")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["document_id"] == sample_pdf_document.id
        assert data["total_pages"] == 2
        assert len(data["pages"]) == 2
        assert "SmartSupply Electronics" in data["pages"][0]["extracted_text"]
    finally:
        app.dependency_overrides.clear()


def test_api_chunks_endpoint(test_db: Session, mock_user: User, sample_pdf_document: Document):
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    try:
        res = client.get(
            f"/api/v1/documents/{sample_pdf_document.id}/chunks",
            params={"chunk_size": 600, "overlap": 100},
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["document_id"] == sample_pdf_document.id
        assert data["total_chunks"] >= 2
        assert data["chunk_size"] == 600
        assert data["overlap"] == 100
        assert "chunk_id" in data["chunks"][0]
        assert data["chunks"][0]["page_number"] == 1
    finally:
        app.dependency_overrides.clear()


def test_api_chunks_endpoint_invalid_overlap(test_db: Session, mock_user: User, sample_pdf_document: Document):
    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    try:
        res = client.get(
            f"/api/v1/documents/{sample_pdf_document.id}/chunks",
            params={"chunk_size": 200, "overlap": 300},
        )
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "overlap" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()
