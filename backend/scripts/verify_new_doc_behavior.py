import io
import sys
import os
import pymupdf

# Set backend directory
sys.path.insert(0, r"c:\irwa project\backend")

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.user import User, UserRole
from app.dependencies.auth import get_current_user
from app.services.chroma_service import _get_collection

def run_verification():
    db = SessionLocal()
    initial_docs = db.query(Document).filter(Document.is_active == True).all()
    initial_doc_ids = {d.id for d in initial_docs}
    print(f"=== INITIAL STATE ===")
    print(f"Active documents in DB: {len(initial_docs)} (IDs: {sorted(initial_doc_ids)})")
    col = _get_collection()
    initial_vector_count = col.count()
    print(f"Initial Chroma vector count: {initial_vector_count}")

    # Set up client with admin authentication override
    admin_user = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    if not admin_user:
        admin_user = User(id=1, email="admin@smartsupply.lk", role=UserRole.ADMIN.value, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    client = TestClient(app)

    # 1. Generate distinctive temporary PDF
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        "Quantum Shield Security Protocol 2026: Mandatory quantum-resistant cryptographic key exchange across all Colombo fulfillment hubs."
    )
    pdf_bytes = doc.tobytes()

    print("\n=== STEP 1: UPLOAD NEW DOCUMENT ===")
    res_upload = client.post(
        "/api/v1/documents",
        data={
            "title": "Quantum Shield Security Protocol 2026",
            "document_type": "procurement_policy",
        },
        files={
            "file": ("quantum_shield_protocol.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
        },
    )
    print("Upload status:", res_upload.status_code)
    upload_data = res_upload.json()
    new_doc_id = upload_data["id"]
    print(f"Created Document ID: {new_doc_id}")
    print(f"Upload Response Title: {upload_data['title']}")
    print(f"Upload Response Indexed status: {upload_data.get('indexed')}")
    print(f"Current Chroma vector count: {col.count()}")

    # 2. Check index status endpoint
    res_status = client.get(f"/api/v1/documents/{new_doc_id}/index-status")
    print(f"Index status endpoint response: {res_status.json()}")

    # 3. Immediately search WITHOUT manually calling reindex
    print("\n=== STEP 2: IMMEDIATE SEMANTIC RETRIEVAL (NO REINDEX) ===")
    query = "What cryptographic exchange is mandatory under Quantum Shield Security Protocol?"
    res_search = client.post(
        "/api/v1/documents/search",
        json={"query": query, "top_k": 3},
    )
    print("Search HTTP Status:", res_search.status_code)
    hits = res_search.json()
    print(f"Returned hits: {len(hits)}")
    for hit in hits:
        print(f"Rank {hit['rank']} | Doc ID: {hit['document_id']} | Title: '{hit['document_title']}' | Distance: {hit['distance']:.4f}")
        print(f"Excerpt: {hit['text'][:140]}...")

    top_hit = hits[0] if hits else None
    assert top_hit is not None
    assert top_hit["document_id"] == new_doc_id, f"Expected top hit to be {new_doc_id}, got {top_hit['document_id']}"
    print("\n>>> CONFIRMED: Newly uploaded document was immediately retrieved without reindex! <<<")

    # 4. Clean up temporary test document
    print("\n=== STEP 3: CLEAN UP TEMPORARY DOCUMENT ===")
    res_delete = client.delete(f"/api/v1/documents/{new_doc_id}")
    print(f"Delete HTTP status: {res_delete.status_code}")

    # 5. Verify vectors and DB state
    after_vector_count = col.count()
    print(f"Chroma vector count after delete: {after_vector_count}")
    assert after_vector_count == initial_vector_count, f"Expected vector count {initial_vector_count}, got {after_vector_count}"

    # Search again to confirm no longer retrieved
    res_search_after = client.post(
        "/api/v1/documents/search",
        json={"query": query, "top_k": 3},
    )
    hits_after = res_search_after.json()
    assert not any(h["document_id"] == new_doc_id for h in hits_after)
    print(">>> CONFIRMED: Deleted document is no longer in Chroma search results! <<<")

    db.close()
    app.dependency_overrides.clear()
    print("\n=== ALL VERIFICATIONS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_verification()
