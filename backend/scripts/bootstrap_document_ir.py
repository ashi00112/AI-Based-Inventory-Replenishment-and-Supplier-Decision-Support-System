"""
SmartSupply Electronics — Document IR Bootstrap & Restoration Script.

Provides an idempotent bootstrap command for developers, fresh clones, and CI/CD:
- Inspects existing PostgreSQL documents, local storage, and Chroma vector store.
- Restores/regenerates ONLY known SmartSupply demo PDFs when needed.
- Indexes documents using the normal production document pipeline.
- Avoids duplicate records and guarantees complete idempotency.
- Never fabricates or generates arbitrary content for non-demo documents.
- Prints a concise summary of active docs, indexed docs, failed docs, vector count, and actions performed.
"""

import hashlib
import io
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.document import Document, DocumentType, IndexStatus
from app.models.supplier import Supplier
from app.services.chroma_service import (
    _get_collection,
    auto_index_document,
    reconcile_index_state,
)
from app.services.document_service import (
    create_document,
    get_secure_file_path,
    get_storage_dir,
)
from scripts.generate_and_upload_demo_docs import (
    generate_digital_distribution_sla,
    generate_digital_performance_review,
    generate_inventory_replenishment_policy,
    generate_nextgen_performance_review,
    generate_nextgen_sla,
    generate_performance_review,
    generate_procurement_policy,
    generate_techsource_performance_review,
    generate_techsource_sla,
)

logger = logging.getLogger("bootstrap_document_ir")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_known_demo_specs(supplier_map: Dict[str, int]) -> List[Dict[str, Any]]:
    """Returns specifications for deterministic SmartSupply demo documents."""
    techsource_id = supplier_map.get("TechSource Lanka")
    digital_id = supplier_map.get("Digital Distribution Lanka")
    nextgen_id = supplier_map.get("NextGen Supplies")

    return [
        {
            "id_tag": "DOC-1",
            "title": "SmartSupply Procurement Policy 2026",
            "alternate_titles": ["SmartSupply Electronics Corporate Procurement Policy"],
            "document_type": DocumentType.PROCUREMENT_POLICY.value,
            "supplier_id": None,
            "filename": "smartsupply_procurement_policy_2026.pdf",
            "generator": lambda p: generate_procurement_policy(p),
        },
        {
            "id_tag": "DOC-2",
            "title": "SmartSupply Inventory Replenishment Policy 2026",
            "alternate_titles": ["Inventory Replenishment & Safety Stock Operational Guidelines"],
            "document_type": DocumentType.INVENTORY_REPLENISHMENT_POLICY.value,
            "supplier_id": None,
            "filename": "smartsupply_inventory_replenishment_policy_2026.pdf",
            "generator": lambda p: generate_inventory_replenishment_policy(p),
        },
        {
            "id_tag": "DOC-3",
            "title": "TechSource Lanka Service Level Agreement",
            "alternate_titles": [],
            "document_type": DocumentType.SUPPLIER_SLA.value,
            "supplier_id": techsource_id,
            "filename": "techsource_lanka_sla_2026.pdf",
            "generator": lambda p: generate_techsource_sla(p, techsource_id),
        },
        {
            "id_tag": "DOC-4",
            "title": "Digital Distribution Lanka Service Level Agreement",
            "alternate_titles": [],
            "document_type": DocumentType.SUPPLIER_SLA.value,
            "supplier_id": digital_id,
            "filename": "digital_distribution_lanka_sla_2026.pdf",
            "generator": lambda p: generate_digital_distribution_sla(p, digital_id),
        },
        {
            "id_tag": "DOC-5",
            "title": "NextGen Supplies Service Level Agreement",
            "alternate_titles": [],
            "document_type": DocumentType.SUPPLIER_SLA.value,
            "supplier_id": nextgen_id,
            "filename": "nextgen_supplies_sla_2026.pdf",
            "generator": lambda p: generate_nextgen_sla(p, nextgen_id),
        },
        {
            "id_tag": "DOC-6",
            "title": "TechSource Lanka Performance Review — Q3 2026",
            "alternate_titles": [
                "Supplier Performance Review — Q3 2026",
                "Supplier Performance Review – Q3 2026",
                "Supplier Performance Review - Q3 2026",
            ],
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": techsource_id,
            "filename": "supplier_performance_review_q3_2026_techsource.pdf",
            "generator": lambda p: generate_techsource_performance_review(p, techsource_id),
        },
        {
            "id_tag": "DOC-7",
            "title": "Digital Distribution Lanka Performance Review — Q3 2026",
            "alternate_titles": [],
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": digital_id,
            "filename": "supplier_performance_review_q3_2026_digital.pdf",
            "generator": lambda p: generate_digital_performance_review(p, digital_id),
        },
        {
            "id_tag": "DOC-8",
            "title": "NextGen Supplies Performance Review — Q3 2026",
            "alternate_titles": [],
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": nextgen_id,
            "filename": "supplier_performance_review_q3_2026_nextgen.pdf",
            "generator": lambda p: generate_nextgen_performance_review(p, nextgen_id),
        },
    ]


def bootstrap_document_ir(db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Main idempotent bootstrap routine:
    1. Inspects existing PostgreSQL documents, storage, and Chroma vector store.
    2. Restores or uploads the 6 known SmartSupply demo documents when missing or unindexed.
    3. Safely flags missing source files for arbitrary non-demo records without hallucinating content.
    4. Purges stale/orphan vectors.
    5. Returns a structured summary dict with accurate counts.
    """
    session = db
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    actions_performed: List[str] = []
    temp_dir = Path(settings.DOCUMENT_STORAGE_DIR).parent / "demo_bootstrap_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage_dir = get_storage_dir()
    current_version = getattr(settings, "DOCUMENT_INDEX_VERSION", "v1")

    try:
        # 1. Resolve suppliers for SLA documents
        suppliers = session.scalars(select(Supplier)).all()
        supplier_map = {s.name: s.id for s in suppliers}
        demo_specs = get_known_demo_specs(supplier_map)

        # 2. Map existing active documents by title
        active_docs = session.query(Document).filter(Document.is_active == True).all()
        doc_by_title: Dict[str, Document] = {d.title.strip().lower(): d for d in active_docs}

        # 3. Process known demo documents
        for spec in demo_specs:
            spec_title = spec["title"]
            all_candidate_titles = [spec_title] + spec.get("alternate_titles", [])
            existing_doc = None
            for t in all_candidate_titles:
                if t.strip().lower() in doc_by_title:
                    existing_doc = doc_by_title[t.strip().lower()]
                    break

            if existing_doc is None:
                # Fresh clone or demo doc never uploaded: generate and upload via production pipeline
                temp_pdf = temp_dir / spec["filename"]
                spec["generator"](str(temp_pdf))
                pdf_bytes = temp_pdf.read_bytes()

                upload_file = UploadFile(
                    filename=spec["filename"],
                    file=io.BytesIO(pdf_bytes),
                    headers={"content-type": "application/pdf"},
                )

                created_doc = create_document(
                    db=session,
                    title=spec_title,
                    document_type=spec["document_type"],
                    file=upload_file,
                    supplier_id=spec["supplier_id"],
                )
                auto_index_document(db=session, document_id=created_doc.id)
                actions_performed.append(f"Created and indexed demo document: '{created_doc.title}' (ID {created_doc.id})")
                doc_by_title[spec_title.strip().lower()] = created_doc

            else:
                # Record exists in DB: verify physical PDF and vector consistency
                file_path = os.path.join(storage_dir, os.path.basename(existing_doc.storage_key))
                pdf_exists = os.path.isfile(file_path)

                if not pdf_exists:
                    # Known demo document with missing local file on fresh clone: regenerate to storage_key
                    spec["generator"](file_path)
                    pdf_bytes = Path(file_path).read_bytes()
                    existing_doc.file_size_bytes = len(pdf_bytes)
                    existing_doc.sha256_checksum = hashlib.sha256(pdf_bytes).hexdigest()
                    existing_doc.index_status = IndexStatus.PENDING.value
                    existing_doc.index_error = None
                    session.commit()
                    session.refresh(existing_doc)

                    auto_index_document(db=session, document_id=existing_doc.id)
                    actions_performed.append(f"Restored missing source PDF and reindexed demo document: '{existing_doc.title}' (ID {existing_doc.id})")
                else:
                    # File exists: check if vectors are present in Chroma
                    collection = _get_collection()
                    v_res = collection.get(where={"document_id": existing_doc.id})
                    has_vectors = len(v_res.get("ids", [])) > 0
                    wrong_ver = existing_doc.index_version != current_version

                    if not has_vectors or existing_doc.index_status != IndexStatus.INDEXED.value or wrong_ver:
                        auto_index_document(db=session, document_id=existing_doc.id)
                        actions_performed.append(f"Reindexed existing demo document into Chroma: '{existing_doc.title}' (ID {existing_doc.id})")

        # 4. Handle non-demo active documents
        known_titles_lower = set()
        for s in demo_specs:
            known_titles_lower.add(s["title"].strip().lower())
            for alt in s.get("alternate_titles", []):
                known_titles_lower.add(alt.strip().lower())

        remaining_docs = session.query(Document).filter(Document.is_active == True).all()
        for doc in remaining_docs:
            if doc.title.strip().lower() in known_titles_lower:
                continue

            file_path = os.path.join(storage_dir, os.path.basename(doc.storage_key)) if doc.storage_key else ""
            pdf_exists = bool(file_path and os.path.isfile(file_path))

            if not pdf_exists:
                # Do NOT invent/regenerate arbitrary content for non-demo records
                expected_err = "Physical source file missing from storage; requires reupload/restoration"
                if doc.index_status != IndexStatus.FAILED.value or doc.index_error != expected_err:
                    doc.index_status = IndexStatus.FAILED.value
                    doc.index_error = expected_err
                    session.commit()
                    actions_performed.append(f"Flagged missing source file for non-demo document: '{doc.title}' (ID {doc.id})")
            else:
                collection = _get_collection()
                v_res = collection.get(where={"document_id": doc.id})
                has_vectors = len(v_res.get("ids", [])) > 0
                if not has_vectors or doc.index_status != IndexStatus.INDEXED.value:
                    auto_index_document(db=session, document_id=doc.id)
                    actions_performed.append(f"Reindexed non-demo document: '{doc.title}' (ID {doc.id})")

        # 5. Final reconciliation to purge orphan / inactive vectors
        reconcile_index_state(db=session, repair=True)

        # 6. Gather authoritative final counts
        final_active_docs = session.query(Document).filter(Document.is_active == True).all()
        active_count = len(final_active_docs)
        indexed_count = sum(1 for d in final_active_docs if d.index_status == IndexStatus.INDEXED.value)
        failed_count = sum(1 for d in final_active_docs if d.index_status == IndexStatus.FAILED.value)

        collection = _get_collection()
        vector_count = collection.count()

        summary = {
            "active_docs": active_count,
            "indexed_docs": indexed_count,
            "failed_docs": failed_count,
            "vector_count": vector_count,
            "actions_performed": actions_performed,
        }

        # Print concise report
        print("\n" + "=" * 50)
        print("SMARTSUPPLY DOCUMENT IR BOOTSTRAP SUMMARY")
        print("=" * 50)
        print(f"Active Documents:   {active_count}")
        print(f"Indexed Documents:  {indexed_count}")
        print(f"Failed Documents:   {failed_count}")
        print(f"Vector Count:       {vector_count}")
        print(f"Actions Performed:  {len(actions_performed)}")
        if actions_performed:
            for act in actions_performed:
                print(f"  • {act}")
        else:
            print("  • None (Corpus is already synchronized and healthy)")
        print("=" * 50 + "\n")

        return summary

    finally:
        # Clean up temporary generation directory
        if temp_dir.exists():
            for f in temp_dir.glob("*"):
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass

        if close_session:
            session.close()


if __name__ == "__main__":
    bootstrap_document_ir()
