import hashlib
import io
import os
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.document import Document, DocumentType
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentValidationError,
    SupplierNotFoundError,
    delete_document,
    get_secure_file_path,
    get_storage_dir,
    update_document,
)
from app.schemas.document import DocumentUpdate

# Dummy valid PDF payload
DUMMY_PDF_CONTENT = b"%PDF-1.4\n%test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


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
    """Creates a sample active user in the database."""
    user = User(
        email="docuser@example.com",
        name="Document Tester",
        role=UserRole.ADMIN.value,
        password_hash="fakehashedpassword",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def mock_supplier(test_db: Session) -> Supplier:
    """Creates a sample supplier in the database."""
    supplier = Supplier(
        supplier_code="DOC-SUP-001",
        name="DocTest Supplies Lanka",
        contact_name="Sunil Perera",
        email="sunil@doctest.lk",
        phone="+94 11 999 8888",
        address="100 Galle Road, Colombo",
        is_active=True,
    )
    test_db.add(supplier)
    test_db.commit()
    test_db.refresh(supplier)
    return supplier


@pytest.fixture
def client(test_db: Session, mock_user: User, tmp_path, monkeypatch):
    """FastAPI TestClient with overridden DB session, current user, and temporary storage path."""
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path / "documents"))
    monkeypatch.setattr(settings, "MAX_PDF_UPLOAD_SIZE_MB", 2)  # 2MB limit for tests

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestDocumentUploadAndValidation:
    """Tests covering upload validation, storage, and security rules."""

    def test_upload_valid_pdf_successfully(self, client: TestClient, mock_supplier: Supplier):
        """1, 2, 3, 4, 5, 6, 35. Upload valid PDF, verify metadata, physical storage, server UUID key, original filename, and checksum."""
        file_bytes = DUMMY_PDF_CONTENT
        expected_sha256 = hashlib.sha256(file_bytes).hexdigest()

        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Vendor SLA Agreement 2026",
                "document_type": DocumentType.SUPPLIER_SLA.value,
                "supplier_id": mock_supplier.id,
            },
            files={
                "file": ("Vendor_Agreement_Final.pdf", io.BytesIO(file_bytes), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # 2. Metadata stored correctly
        assert data["title"] == "Vendor SLA Agreement 2026"
        assert data["document_type"] == DocumentType.SUPPLIER_SLA.value
        assert data["supplier_id"] == mock_supplier.id
        assert data["supplier"]["supplier_code"] == "DOC-SUP-001"
        assert data["file_size_bytes"] == len(file_bytes)
        assert data["is_active"] is True

        # 5. Original filename retained as metadata
        assert data["original_filename"] == "Vendor_Agreement_Final.pdf"

        # 35. Checksum is correct
        assert data["sha256_checksum"] == expected_sha256

        # 3, 4. Physical file stored with server-generated UUID key
        storage_dir = get_storage_dir()
        files_on_disk = os.listdir(storage_dir)
        assert len(files_on_disk) == 1
        stored_filename = files_on_disk[0]
        assert stored_filename.endswith(".pdf")
        assert stored_filename != "Vendor_Agreement_Final.pdf"  # Server-generated
        with open(os.path.join(storage_dir, stored_filename), "rb") as f:
            assert f.read() == file_bytes

    def test_non_pdf_extension_rejected(self, client: TestClient, mock_supplier: Supplier):
        """7. Files without .pdf extension are rejected."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Spreadsheet",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
                "supplier_id": mock_supplier.id,
            },
            files={
                "file": ("contract.xlsx", io.BytesIO(b"dummy data"), "application/vnd.ms-excel"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Only PDF documents (.pdf extension) are accepted" in response.json()["detail"]

    def test_wrong_mime_type_rejected(self, client: TestClient, mock_supplier: Supplier):
        """8. Non-PDF MIME type is rejected."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Image disguised as pdf",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
                "supplier_id": mock_supplier.id,
            },
            files={
                "file": ("contract.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "image/png"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid content type" in response.json()["detail"]

    def test_fake_pdf_without_magic_signature_rejected(self, client: TestClient, mock_supplier: Supplier):
        """9. Fake PDF without %PDF- magic bytes rejected."""
        fake_content = b"This is just plain text masquerading as a PDF file"
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Fake PDF",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
                "supplier_id": mock_supplier.id,
            },
            files={
                "file": ("fake.pdf", io.BytesIO(fake_content), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "%PDF- signature" in response.json()["detail"]

    def test_empty_file_rejected(self, client: TestClient, mock_supplier: Supplier):
        """10. Empty file (0 bytes) is rejected."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Empty File",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
                "supplier_id": mock_supplier.id,
            },
            files={
                "file": ("empty.pdf", io.BytesIO(b""), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "empty" in response.json()["detail"].lower()

    def test_oversized_pdf_rejected(self, client: TestClient, mock_supplier: Supplier):
        """11. File exceeding configured size limit (2MB) is rejected."""
        # Create a payload larger than 2MB
        big_content = b"%PDF-" + b"0" * (2 * 1024 * 1024 + 500)
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Oversized File",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
                "supplier_id": mock_supplier.id,
            },
            files={
                "file": ("big.pdf", io.BytesIO(big_content), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "exceeds the maximum allowed limit" in response.json()["detail"]

    def test_supplier_sla_requires_supplier(self, client: TestClient):
        """12. Supplier SLA requires supplier_id."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "SLA without supplier",
                "document_type": DocumentType.SUPPLIER_SLA.value,
            },
            files={
                "file": ("sla.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "must be associated with a valid supplier" in response.json()["detail"]

    def test_supplier_contract_requires_supplier(self, client: TestClient):
        """13. Supplier contract requires supplier_id."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Contract without supplier",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
            },
            files={
                "file": ("contract.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_supplier_performance_report_requires_supplier(self, client: TestClient):
        """14. Supplier performance report requires supplier_id."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Report without supplier",
                "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            },
            files={
                "file": ("report.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_nonexistent_supplier_rejected(self, client: TestClient):
        """15. Referencing a nonexistent supplier returns 404."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Contract with bogus supplier",
                "document_type": DocumentType.SUPPLIER_CONTRACT.value,
                "supplier_id": 999999,
            },
            files={
                "file": ("contract.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Supplier with ID 999999 not found" in response.json()["detail"]

    def test_procurement_policy_works_without_supplier(self, client: TestClient):
        """16. Procurement policy works without supplier and disallows linking supplier."""
        # 16a. Success without supplier
        res_ok = client.post(
            "/api/v1/documents",
            data={
                "title": "Company Procurement Policy 2026",
                "document_type": DocumentType.PROCUREMENT_POLICY.value,
            },
            files={
                "file": ("proc_policy.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert res_ok.status_code == status.HTTP_201_CREATED
        assert res_ok.json()["supplier_id"] is None

        # 16b. Rejected if supplier_id is provided
        res_bad = client.post(
            "/api/v1/documents",
            data={
                "title": "Company Procurement Policy with Supplier",
                "document_type": DocumentType.PROCUREMENT_POLICY.value,
                "supplier_id": 1,
            },
            files={
                "file": ("proc_policy2.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert res_bad.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "cannot be linked to a supplier" in res_bad.json()["detail"]

    def test_inventory_replenishment_policy_works_without_supplier(self, client: TestClient):
        """17. Inventory Replenishment policy works without supplier and disallows linking supplier."""
        res_ok = client.post(
            "/api/v1/documents",
            data={
                "title": "Replenishment Rules 2026",
                "document_type": DocumentType.INVENTORY_REPLENISHMENT_POLICY.value,
            },
            files={
                "file": ("replenish.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert res_ok.status_code == status.HTTP_201_CREATED
        assert res_ok.json()["supplier_id"] is None

    def test_path_traversal_filename_sanitized(self, client: TestClient):
        """34. Malicious path traversal filenames are sanitized and cannot escape storage."""
        response = client.post(
            "/api/v1/documents",
            data={
                "title": "Exploit Attempt",
                "document_type": DocumentType.PROCUREMENT_POLICY.value,
            },
            files={
                "file": ("../../../../etc/passwd.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf"),
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Original filename should be stripped of directory traversal components
        assert "/" not in data["original_filename"]
        assert "\\" not in data["original_filename"]
        assert data["original_filename"] == "passwd.pdf"


class TestDocumentCRUDAndFiltering:
    """Tests covering document listing, filtering, search, update, download, and deletion."""

    def test_list_and_filter_documents(self, client: TestClient, mock_supplier: Supplier, test_db: Session):
        """18, 19, 20, 21, 22. List, filter by document_type, supplier_id, is_active, and text search."""
        # Create second supplier
        s2 = Supplier(supplier_code="DOC-SUP-002", name="Second Tech Wholesale Lanka", is_active=True)
        test_db.add(s2)
        test_db.commit()
        test_db.refresh(s2)

        # Upload 3 documents
        d1 = client.post(
            "/api/v1/documents",
            data={"title": "TechSource SLA 2026", "document_type": DocumentType.SUPPLIER_SLA.value, "supplier_id": mock_supplier.id},
            files={"file": ("techsource_sla.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()

        d2 = client.post(
            "/api/v1/documents",
            data={"title": "Wholesale Master Contract", "document_type": DocumentType.SUPPLIER_CONTRACT.value, "supplier_id": s2.id},
            files={"file": ("wholesale_contract.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()

        d3 = client.post(
            "/api/v1/documents",
            data={"title": "Standard Procurement Guidelines", "document_type": DocumentType.PROCUREMENT_POLICY.value},
            files={"file": ("guidelines.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()

        # 18. List all documents
        res_all = client.get("/api/v1/documents")
        assert res_all.status_code == status.HTTP_200_OK
        assert len(res_all.json()) >= 3

        # 19. Filter by document_type
        res_type = client.get(f"/api/v1/documents?document_type={DocumentType.SUPPLIER_SLA.value}")
        assert res_type.status_code == status.HTTP_200_OK
        data_type = res_type.json()
        assert len(data_type) == 1
        assert data_type[0]["id"] == d1["id"]

        # 20. Filter by supplier
        res_sup = client.get(f"/api/v1/documents?supplier_id={s2.id}")
        assert res_sup.status_code == status.HTTP_200_OK
        data_sup = res_sup.json()
        assert len(data_sup) == 1
        assert data_sup[0]["id"] == d2["id"]

        # 21. Active filtering
        client.patch(f"/api/v1/documents/{d3['id']}", json={"is_active": False})
        res_active = client.get("/api/v1/documents?is_active=true")
        active_ids = [d["id"] for d in res_active.json()]
        assert d3["id"] not in active_ids

        res_inactive = client.get("/api/v1/documents?is_active=false")
        inactive_ids = [d["id"] for d in res_inactive.json()]
        assert d3["id"] in inactive_ids

        # 22. Text search
        res_search = client.get("/api/v1/documents?search=Master")
        assert res_search.status_code == status.HTTP_200_OK
        search_data = res_search.json()
        assert len(search_data) == 1
        assert search_data[0]["id"] == d2["id"]

    def test_get_document(self, client: TestClient, mock_supplier: Supplier):
        """23, 28. Get single document by ID and verify 404 on missing document."""
        upload_res = client.post(
            "/api/v1/documents",
            data={"title": "Detail Test Doc", "document_type": DocumentType.SUPPLIER_SLA.value, "supplier_id": mock_supplier.id},
            files={"file": ("detail.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()
        doc_id = upload_res["id"]

        # 23. Get document
        res = client.get(f"/api/v1/documents/{doc_id}")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["title"] == "Detail Test Doc"

        # 28. Missing document returns 404
        res_missing = client.get("/api/v1/documents/999999")
        assert res_missing.status_code == status.HTTP_404_NOT_FOUND

    def test_update_document_metadata_and_revalidate(self, client: TestClient, mock_supplier: Supplier):
        """24, 25, 26. Update title, revalidate rules on document_type update, and prevent patch of storage metadata."""
        upload_res = client.post(
            "/api/v1/documents",
            data={"title": "Initial Title", "document_type": DocumentType.OTHER.value},
            files={"file": ("initial.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()
        doc_id = upload_res["id"]

        # 24. Update title
        res_title = client.patch(f"/api/v1/documents/{doc_id}", json={"title": "Updated Title"})
        assert res_title.status_code == status.HTTP_200_OK
        assert res_title.json()["title"] == "Updated Title"

        # 25. Updating document_type to supplier_sla without supplier_id revalidates and fails
        res_bad_type = client.patch(
            f"/api/v1/documents/{doc_id}",
            json={"document_type": DocumentType.SUPPLIER_SLA.value},
        )
        assert res_bad_type.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "must be associated with a valid supplier" in res_bad_type.json()["detail"]

        # Now supply supplier_id and update successfully
        res_ok_type = client.patch(
            f"/api/v1/documents/{doc_id}",
            json={
                "document_type": DocumentType.SUPPLIER_SLA.value,
                "supplier_id": mock_supplier.id,
            },
        )
        assert res_ok_type.status_code == status.HTTP_200_OK
        assert res_ok_type.json()["document_type"] == DocumentType.SUPPLIER_SLA.value
        assert res_ok_type.json()["supplier_id"] == mock_supplier.id

        # 26. Protected immutable storage metadata cannot be arbitrarily patched (extra='forbid')
        res_forbidden_patch = client.patch(
            f"/api/v1/documents/{doc_id}",
            json={"storage_key": "hacked.pdf"},
        )
        assert res_forbidden_patch.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_download_document(self, client: TestClient, mock_supplier: Supplier):
        """27. Download returns exact PDF bytes and headers."""
        file_bytes = DUMMY_PDF_CONTENT
        upload_res = client.post(
            "/api/v1/documents",
            data={"title": "Download Test", "document_type": DocumentType.SUPPLIER_SLA.value, "supplier_id": mock_supplier.id},
            files={"file": ("download_sample.pdf", io.BytesIO(file_bytes), "application/pdf")},
        ).json()
        doc_id = upload_res["id"]

        res = client.get(f"/api/v1/documents/{doc_id}/download")
        assert res.status_code == status.HTTP_200_OK
        assert res.headers["content-type"] == "application/pdf"
        assert res.content == file_bytes
        assert 'filename="download_sample.pdf"' in res.headers["content-disposition"]

    def test_delete_removes_db_and_physical_file(self, client: TestClient, mock_supplier: Supplier, test_db: Session):
        """29, 30, 31. Delete removes DB row and physical file, and handles missing physical file gracefully."""
        upload_res = client.post(
            "/api/v1/documents",
            data={"title": "To Delete", "document_type": DocumentType.SUPPLIER_SLA.value, "supplier_id": mock_supplier.id},
            files={"file": ("to_delete.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()
        doc_id = upload_res["id"]

        doc_record = test_db.get(Document, doc_id)
        storage_path = get_secure_file_path(doc_record.storage_key)
        assert os.path.exists(storage_path)

        # 29, 30. Delete document
        del_res = client.delete(f"/api/v1/documents/{doc_id}")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

        # Verify DB row removed
        assert test_db.get(Document, doc_id) is None
        # Verify physical file removed
        assert not os.path.exists(storage_path)

        # 31. Deleting metadata when physical file is already absent handled safely
        upload_res2 = client.post(
            "/api/v1/documents",
            data={"title": "Orphan File Test", "document_type": DocumentType.OTHER.value},
            files={"file": ("orphan.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()
        doc_id2 = upload_res2["id"]
        doc2 = test_db.get(Document, doc_id2)
        p2 = get_secure_file_path(doc2.storage_key)
        # Pre-delete physical file
        os.remove(p2)

        # Delete should still succeed and remove DB row
        del_res2 = client.delete(f"/api/v1/documents/{doc_id2}")
        assert del_res2.status_code == status.HTTP_204_NO_CONTENT
        assert test_db.get(Document, doc_id2) is None

    def test_supplier_deletion_sets_document_supplier_id_null(self, client: TestClient, test_db: Session):
        """33. Deleting a supplier sets linked document supplier_id to NULL via SET NULL."""
        s = Supplier(supplier_code="DOC-SUP-DEL", name="Delete Me Vendor", is_active=True)
        test_db.add(s)
        test_db.commit()
        test_db.refresh(s)

        upload_res = client.post(
            "/api/v1/documents",
            data={"title": "Vendor Contract", "document_type": DocumentType.SUPPLIER_CONTRACT.value, "supplier_id": s.id},
            files={"file": ("contract_del.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        ).json()
        doc_id = upload_res["id"]

        # Delete the supplier directly
        test_db.delete(s)
        test_db.commit()

        # Document must still exist with supplier_id == None
        test_db.expire_all()
        doc = test_db.get(Document, doc_id)
        assert doc is not None
        assert doc.supplier_id is None

    def test_db_failure_cleans_up_newly_written_file(self, client: TestClient, monkeypatch, tmp_path):
        """32. Database failure during upload cleans up newly written physical file."""
        from sqlalchemy.orm import Session
        storage_dir = get_storage_dir()

        # Monkeypatch db.commit to raise an exception simulating database failure
        def mock_commit(self):
            raise RuntimeError("Simulated database failure during document commit")

        monkeypatch.setattr(Session, "commit", mock_commit)

        # Count files before upload attempt
        initial_files = set(os.listdir(storage_dir))

        response = client.post(
            "/api/v1/documents",
            data={"title": "Failing Document", "document_type": DocumentType.PROCUREMENT_POLICY.value},
            files={"file": ("failing.pdf", io.BytesIO(DUMMY_PDF_CONTENT), "application/pdf")},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Files on disk must remain unchanged (no orphaned file left)
        final_files = set(os.listdir(storage_dir))
        assert final_files == initial_files

