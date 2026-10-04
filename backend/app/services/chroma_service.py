import os
import re
import time
import logging
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api import Collection

logger = logging.getLogger(__name__)
from app.core.config import settings
from app.services.embedding_service import EmbeddingProvider
from app.models.document import Document, IndexStatus
from app.schemas.document_processing import DocumentChunkResponse

_client_instance = None


def sanitize_error_message(err: Any) -> str:
    """
    Sanitizes an exception or error string to ensure no internal filesystem paths,
    database credentials, secrets, or raw tracebacks are exposed.
    """
    if err is None:
        return ""
    text = str(err).strip()
    if not text:
        return "Unknown error"

    # Redact database connection strings first (before path regexes)
    text = re.sub(r"[a-zA-Z0-9_\+]+://[^\s@]+@[^\s/]+(?:\/[^\s]+)?", "[REDACTED_DB_URL]", text)

    # Redact passwords/tokens/keys
    text = re.sub(r"(?i)(password|secret|token|key|pwd)\s*[=:]\s*['\"]?[^\s'\"]+['\"]?", r"\1=[REDACTED]", text)

    # Redact common path patterns (Windows C:\... and Unix /...)
    text = re.sub(r"[A-Za-z]:\\[\w\s\-\.\\]+", "[REDACTED_PATH]", text)
    text = re.sub(r"(?<!/)/(?:[a-zA-Z0-9_\-\.]+/)+[a-zA-Z0-9_\-\.]*", "[REDACTED_PATH]", text)

    first_line = text.split("\n")[0].strip()
    return first_line[:255]


def reset_chroma_client() -> None:
    """Resets the singleton Chromadb client, forcing the next call to re-read settings."""
    global _client_instance
    _client_instance = None


def _get_client():
    """Create a singleton Chromadb client pointing to persistent storage.

    The client is configured to store data in ``settings.CHROMA_PERSIST_DIR``.
    Automatically detects path changes (e.g. during isolated testing) and re-instantiates.
    """
    global _client_instance
    persist_dir = getattr(settings, "CHROMA_PERSIST_DIR", None)
    if not persist_dir:
        raise RuntimeError("CHROMA_PERSIST_DIR is not configured in settings.")

    norm_persist_dir = os.path.abspath(persist_dir)
    current_path = getattr(_client_instance, "_persist_dir", None) if _client_instance is not None else None
    if _client_instance is None or current_path != norm_persist_dir:
        os.makedirs(norm_persist_dir, exist_ok=True)
        _client_instance = chromadb.PersistentClient(path=norm_persist_dir)
        _client_instance._persist_dir = norm_persist_dir
    return _client_instance


def _get_collection() -> Collection:
    """Retrieve (or create) the dedicated collection for SmartSupply documents."""
    collection_name = getattr(settings, "CHROMA_COLLECTION_NAME", "smartsupply_documents")
    client = _get_client()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        collection = client.create_collection(name=collection_name)
    return collection


def index_document_chunks(document_id: int, chunks: List[DocumentChunkResponse]) -> None:
    """Upsert a list of deterministic chunks for a document into Chroma.

    Existing vectors for the same chunk IDs are overwritten, ensuring deterministic
    re‑indexing without duplication.
    """
    if not chunks:
        return
    collection = _get_collection()
    ids = [chunk.chunk_id for chunk in chunks]
    texts = [chunk.text for chunk in chunks]
    embeddings = EmbeddingProvider.embed_texts(texts)
    metadatas: List[Dict[str, Any]] = []
    for chunk in chunks:
        meta: Dict[str, Any] = {
            "document_id": chunk.document_id,
            "document_title": chunk.document_title,
            "document_type": chunk.document_type,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
        }
        if chunk.supplier_id is not None:
            meta["supplier_id"] = chunk.supplier_id
        metadatas.append(meta)
    collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)


def delete_document_vectors(document_id: int) -> None:
    """Remove all vectors belonging to a given document from the collection."""
    try:
        collection = _get_collection()
        results = collection.get(where={"document_id": document_id})
        ids: List[str] = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
            logger.info("Deleted %d vectors from Chroma for document_id=%d", len(ids), document_id)
        else:
            logger.info("No vectors found in Chroma to delete for document_id=%d", document_id)
    except Exception as exc:
        logger.error("Failed to delete vectors from Chroma for document_id=%d: %s", document_id, sanitize_error_message(exc))
        raise


def is_document_indexed(document_id: int) -> bool:
    """Check whether Chroma contains at least one vector for document_id."""
    try:
        collection = _get_collection()
        results = collection.get(where={"document_id": document_id})
        return len(results.get("ids", [])) > 0
    except Exception as exc:
        logger.warning("Failed to check index status for document_id=%d: %s", document_id, sanitize_error_message(exc))
        return False


def get_document_index_status(document_id: int, db: Optional[Any] = None) -> Dict[str, Any]:
    """Return comprehensive indexing status for document_id combining PostgreSQL metadata
    with ChromaDB vector consistency checks.
    """
    session = db
    close_session = False
    if session is None:
        from app.database.session import SessionLocal
        session = SessionLocal()
        close_session = True

    try:
        doc = session.get(Document, document_id)
        if not doc:
            return {
                "document_id": document_id,
                "indexed": False,
                "chunk_count": 0,
                "index_status": IndexStatus.NOT_INDEXED.value,
                "last_indexed_at": None,
                "index_version": None,
                "index_error": "Document not found in database",
                "error": "Document not found in database",
            }

        chroma_ids: List[str] = []
        chroma_error: Optional[str] = None
        try:
            collection = _get_collection()
            results = collection.get(where={"document_id": document_id})
            chroma_ids = results.get("ids", [])
        except Exception as exc:
            chroma_error = sanitize_error_message(exc)
            logger.warning("Failed to retrieve index status for document_id=%d: %s", document_id, chroma_error)

        chunk_count = len(chroma_ids)

        # Content/index consistency check:
        # If DB says indexed but Chroma has zero vectors, report degraded/not-indexed state.
        if doc.index_status == IndexStatus.INDEXED.value and chunk_count == 0:
            return {
                "document_id": document_id,
                "indexed": False,
                "chunk_count": 0,
                "index_status": IndexStatus.NOT_INDEXED.value,
                "last_indexed_at": doc.last_indexed_at,
                "index_version": doc.index_version,
                "index_error": "Vectors missing from vector store (degraded state)",
                "error": "Vectors missing from vector store (degraded state)",
            }

        is_indexed = (doc.index_status == IndexStatus.INDEXED.value and chunk_count > 0)
        return {
            "document_id": document_id,
            "indexed": is_indexed,
            "chunk_count": chunk_count,
            "index_status": doc.index_status,
            "last_indexed_at": doc.last_indexed_at,
            "index_version": doc.index_version,
            "index_error": doc.index_error or chroma_error,
            "error": doc.index_error or chroma_error,
        }
    finally:
        if close_session:
            session.close()


def auto_index_document(db: Any, document_id: int) -> bool:
    """Process and index an active document's chunks into ChromaDB with persistent lifecycle tracking.

    Flow:
    1. If document is inactive: remove vectors from Chroma, mark index_status=not_indexed, return False.
    2. Transition index_status=indexing.
    3. Extract text and segment into deterministic chunks.
    4. Upsert chunks into ChromaDB.
    5. On success: index_status=indexed, last_indexed_at=UTC now, index_version=current, index_error=None.
    6. On failure: index_status=failed, index_error=sanitized error summary.
    """
    from app.services.document_service import get_document
    from app.services.document_processing_service import process_document

    doc = get_document(db=db, document_id=document_id)
    if not doc.is_active:
        logger.info("Document id=%d is not active; removing vectors and setting not_indexed.", document_id)
        delete_document_vectors(document_id=doc.id)
        doc.index_status = IndexStatus.NOT_INDEXED.value
        doc.index_error = None
        db.commit()
        return False

    # Mark as indexing
    doc.index_status = IndexStatus.INDEXING.value
    db.commit()
    db.refresh(doc)

    start_time = time.perf_counter()
    try:
        chunks_response = process_document(db=db, document_id=doc.id)
        if not chunks_response.chunks:
            logger.info("Document id=%d has no text chunks to index.", document_id)
            delete_document_vectors(document_id=doc.id)
            doc.index_status = IndexStatus.NOT_INDEXED.value
            doc.index_error = "No extractable text chunks to index."
            db.commit()
            return False

        # Remove prior vectors before upserting new chunks (idempotent re-indexing)
        delete_document_vectors(document_id=doc.id)
        index_document_chunks(document_id=doc.id, chunks=chunks_response.chunks)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        doc.index_status = IndexStatus.INDEXED.value
        doc.last_indexed_at = datetime.now(timezone.utc)
        doc.index_error = None
        doc.index_version = getattr(settings, "DOCUMENT_INDEX_VERSION", "v1")
        db.commit()
        db.refresh(doc)

        logger.info(
            "Document indexed successfully: document_id=%d, operation=auto_index, status=indexed, chunk_count=%d, duration_ms=%d, index_version=%s",
            doc.id, len(chunks_response.chunks), duration_ms, doc.index_version
        )
        return True

    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        safe_err = sanitize_error_message(exc)
        doc.index_status = IndexStatus.FAILED.value
        doc.index_error = safe_err
        db.commit()
        db.refresh(doc)
        logger.error(
            "Document indexing failed: document_id=%d, operation=auto_index, status=failed, error=%s, duration_ms=%d",
            doc.id, safe_err, duration_ms
        )
        return False


def rebuild_index(active_documents: List[Document], db: Optional[Any] = None) -> Dict[str, int]:
    """Clear the collection and re‑index all provided active documents safely."""
    collection = _get_collection()
    try:
        collection.delete()
    except Exception:
        pass

    session = db
    close_session = False
    if session is None:
        from app.database.session import SessionLocal
        session = SessionLocal()
        close_session = True

    doc_count = 0
    chunk_count = 0
    try:
        for doc in active_documents:
            ok = auto_index_document(db=session, document_id=doc.id)
            if ok:
                doc_count += 1
                status_info = get_document_index_status(document_id=doc.id, db=session)
                chunk_count += status_info.get("chunk_count", 0)
    finally:
        if close_session:
            session.close()

    return {"documents_indexed": doc_count, "chunks_indexed": chunk_count}


def reconcile_index_state(db: Any, repair: bool = True) -> Dict[str, Any]:
    """
    Compares PostgreSQL documents against ChromaDB and filesystem storage,
    safely reconciling lifecycle state and repairing indices.

    Rules:
    - Active doc + source PDF missing -> mark failed ('Physical source file missing from storage; requires reupload/restoration'), purge any vectors, count as missing_source.
    - Active doc + source PDF exists + vectors missing ->
        if repair: re-extract, chunk, embed, and index it via auto_index_document.
        if not repair: mark not_indexed ('Vectors missing from vector store; requires re-indexing').
    - Active doc + source PDF exists + vectors exist + wrong index_version ->
        if repair: reindex via auto_index_document.
        if not repair: record version mismatch error.
    - Active doc + source PDF exists + vectors exist + correct version ->
        ensure index_status=indexed.
    - Inactive doc + vectors exist -> purge vectors from Chroma, mark not_indexed.
    - Stale/orphan vectors from deleted doc IDs -> purge from Chroma.
    """
    from collections import defaultdict
    from app.services.document_service import get_storage_dir

    storage_dir = get_storage_dir()
    docs = db.query(Document).all()
    collection = _get_collection()
    chroma_results = collection.get()
    all_chroma_ids = chroma_results.get("ids", [])
    all_metas = chroma_results.get("metadatas", [])

    chroma_doc_map = defaultdict(list)
    for cid, meta in zip(all_chroma_ids, all_metas):
        if meta and "document_id" in meta:
            chroma_doc_map[meta["document_id"]].append(cid)

    reconciled_count = 0
    indexed_count = 0
    unindexed_count = 0
    deactivated_cleaned_count = 0
    stale_purged_count = 0
    missing_source_count = 0
    reindexed_count = 0

    current_version = getattr(settings, "DOCUMENT_INDEX_VERSION", "v1")

    for doc in docs:
        vector_ids = chroma_doc_map.get(doc.id, [])
        has_vectors = len(vector_ids) > 0
        file_path = os.path.join(storage_dir, os.path.basename(doc.storage_key)) if doc.storage_key else ""
        pdf_exists = bool(file_path and os.path.isfile(file_path))

        if doc.is_active:
            if not pdf_exists:
                # Active document but local PDF source file is missing from disk
                missing_source_count += 1
                if has_vectors:
                    try:
                        collection.delete(ids=vector_ids)
                        deactivated_cleaned_count += len(vector_ids)
                    except Exception as exc:
                        logger.warning("Failed to clean vectors for missing file doc id=%d: %s", doc.id, sanitize_error_message(exc))

                expected_err = "Physical source file missing from storage; requires reupload/restoration"
                if doc.index_status != IndexStatus.FAILED.value or doc.index_error != expected_err:
                    doc.index_status = IndexStatus.FAILED.value
                    doc.index_error = expected_err
                    reconciled_count += 1
                unindexed_count += 1

            elif not has_vectors:
                # Active document, source PDF available, but vectors missing
                if repair:
                    ok = auto_index_document(db=db, document_id=doc.id)
                    if ok:
                        reindexed_count += 1
                        indexed_count += 1
                        reconciled_count += 1
                    else:
                        unindexed_count += 1
                        reconciled_count += 1
                else:
                    if doc.index_status != IndexStatus.NOT_INDEXED.value:
                        doc.index_status = IndexStatus.NOT_INDEXED.value
                        doc.index_error = "Vectors missing from vector store; requires re-indexing"
                        reconciled_count += 1
                    unindexed_count += 1

            else:
                # Active document, source PDF available, vectors present in Chroma
                wrong_version = (doc.index_version != current_version)
                if wrong_version:
                    if repair:
                        ok = auto_index_document(db=db, document_id=doc.id)
                        if ok:
                            reindexed_count += 1
                            indexed_count += 1
                            reconciled_count += 1
                        else:
                            unindexed_count += 1
                            reconciled_count += 1
                    else:
                        doc.index_error = f"Index version mismatch: expected {current_version}, got {doc.index_version}"
                        reconciled_count += 1
                        indexed_count += 1
                else:
                    if doc.index_status != IndexStatus.INDEXED.value or not doc.last_indexed_at:
                        doc.index_status = IndexStatus.INDEXED.value
                        if not doc.last_indexed_at:
                            doc.last_indexed_at = datetime.now(timezone.utc)
                        doc.index_version = current_version
                        doc.index_error = None
                        reconciled_count += 1
                    indexed_count += 1

        else:
            # Inactive document
            if has_vectors:
                try:
                    collection.delete(ids=vector_ids)
                    deactivated_cleaned_count += len(vector_ids)
                except Exception as exc:
                    logger.warning("Failed to clean inactive doc vectors: %s", sanitize_error_message(exc))
            if doc.index_status != IndexStatus.NOT_INDEXED.value:
                doc.index_status = IndexStatus.NOT_INDEXED.value
                doc.index_error = None
                reconciled_count += 1

    # Check for orphan vectors whose document_id does not exist in PostgreSQL at all
    db_doc_ids = {d.id for d in docs}
    orphan_vector_ids = []
    for doc_id, cids in chroma_doc_map.items():
        if doc_id not in db_doc_ids:
            orphan_vector_ids.extend(cids)
    if orphan_vector_ids:
        try:
            collection.delete(ids=orphan_vector_ids)
            stale_purged_count = len(orphan_vector_ids)
            logger.info("Purged %d orphan vectors from Chroma during reconciliation.", stale_purged_count)
        except Exception as exc:
            logger.warning("Failed to purge orphan vectors: %s", sanitize_error_message(exc))

    db.commit()

    logger.info(
        "Reconciliation completed: operation=reconcile_index_state, total_checked=%d, reconciled=%d, active_indexed=%d, active_unindexed=%d, inactive_cleaned=%d, stale_purged=%d, missing_source=%d, reindexed=%d",
        len(docs), reconciled_count, indexed_count, unindexed_count, deactivated_cleaned_count, stale_purged_count, missing_source_count, reindexed_count
    )

    return {
        "total_documents_checked": len(docs),
        "reconciled_count": reconciled_count,
        "active_indexed": indexed_count,
        "active_unindexed": unindexed_count,
        "inactive_vectors_removed": deactivated_cleaned_count,
        "stale_vectors_purged": stale_purged_count,
        "missing_source_count": missing_source_count,
        "reindexed_count": reindexed_count,
    }


def check_document_ir_health(db: Any) -> Dict[str, Any]:
    """
    Checks operational health of the Document IR subsystem:
    - PostgreSQL connectivity & document counts
    - ChromaDB availability & vector count
    - Embedding provider availability
    - Source PDF filesystem availability
    """
    from sqlalchemy import select, func, text
    from app.services.document_service import get_storage_dir

    postgres_connected = False
    active_count = 0
    indexed_count = 0
    failed_count = 0
    missing_source_count = 0
    not_indexed_count = 0
    current_version = getattr(settings, "DOCUMENT_INDEX_VERSION", "v1")

    try:
        db.execute(text("SELECT 1"))
        postgres_connected = True
        active_docs = db.query(Document).filter(Document.is_active == True).all()
        active_count = len(active_docs)
        indexed_count = sum(1 for d in active_docs if d.index_status == IndexStatus.INDEXED.value)
        failed_count = sum(1 for d in active_docs if d.index_status == IndexStatus.FAILED.value)
        not_indexed_count = sum(
            1 for d in active_docs if d.index_status in [IndexStatus.NOT_INDEXED.value, IndexStatus.PENDING.value, IndexStatus.INDEXING.value]
        )

        storage_dir = get_storage_dir()
        for doc in active_docs:
            if not doc.storage_key:
                missing_source_count += 1
            else:
                f_path = os.path.join(storage_dir, os.path.basename(doc.storage_key))
                if not os.path.isfile(f_path):
                    missing_source_count += 1
    except Exception as db_exc:
        postgres_connected = False
        logger.error("PostgreSQL health probe failed: %s", sanitize_error_message(db_exc))

    chroma_available = False
    vector_count = 0
    try:
        collection = _get_collection()
        vector_count = collection.count()
        chroma_available = True
    except Exception as chroma_exc:
        chroma_available = False
        logger.error("ChromaDB health probe failed: %s", sanitize_error_message(chroma_exc))

    embedding_available = False
    try:
        test_emb = EmbeddingProvider.embed_texts(["health_check"])
        embedding_available = len(test_emb) > 0 and len(test_emb[0]) > 0
    except Exception as emb_exc:
        embedding_available = False
        logger.error("Embedding provider health probe failed: %s", sanitize_error_message(emb_exc))

    # Overall status assessment
    if not postgres_connected:
        status_val = "unhealthy"
        details = "Database connection offline."
    elif not chroma_available or not embedding_available:
        status_val = "degraded"
        details = "Vector storage or embedding provider unavailable; structured operations operational."
    elif active_count > 0 and vector_count == 0:
        status_val = "degraded"
        details = f"{active_count} active document(s) in database but vector store has 0 vectors; reconciliation required."
    elif missing_source_count > 0:
        status_val = "degraded"
        details = f"{missing_source_count} active document(s) missing physical source file in storage."
    elif failed_count > 0:
        status_val = "degraded"
        details = f"{failed_count} active document(s) in failed index state."
    elif not_indexed_count > 0 or indexed_count < active_count:
        status_val = "degraded"
        details = f"{active_count - indexed_count} active document(s) not yet indexed."
    else:
        stale_versions = sum(1 for d in active_docs if d.index_version != current_version)
        if stale_versions > 0:
            status_val = "degraded"
            details = f"{stale_versions} document(s) have stale index version (expected {current_version})."
        else:
            status_val = "healthy"
            details = "All Document IR services and models operational."

    return {
        "status": status_val,
        "postgres_connected": postgres_connected,
        "chroma_available": chroma_available,
        "embedding_available": embedding_available,
        "active_document_count": active_count,
        "indexed_document_count": indexed_count,
        "failed_document_count": failed_count,
        "missing_source_count": missing_source_count,
        "vector_count": vector_count,
        "index_version": current_version,
        "details": details,
    }


def search_documents(
    query: str,
    top_k: int = 5,
    document_type: str | None = None,
    supplier_id: int | None = None,
    db: Any | None = None,
) -> List[Dict[str, Any]]:
    """Perform a similarity search over the Chroma collection with DB validation.

    Production hardening guarantees:
    - Input query is non-empty and stripped.
    - top_k is validated within 1..20.
    - Candidate chunks returned by Chroma are verified against PostgreSQL.
    - Documents deleted or deactivated in PostgreSQL are immediately discarded.
    - Stale vectors from missing or inactive documents are safely purged from Chroma.
    - Document title, type, and supplier association are refreshed from PostgreSQL.
    """
    if not query or not query.strip():
        raise ValueError("Query string must be non-empty.")
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20.")

    clean_query = query.strip()
    collection = _get_collection()
    where: Dict[str, Any] = {}
    if document_type:
        where["document_type"] = document_type
    if supplier_id is not None:
        where["supplier_id"] = supplier_id

    # Over-fetch candidates to ensure top_k valid chunks after stale vector filtering
    fetch_limit = min(max(top_k * 3, 10), 50)
    start_time = time.perf_counter()
    query_emb = EmbeddingProvider.embed_texts([clean_query])[0]
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=fetch_limit,
        where=where if where else None,
        include=["documents", "metadatas", "distances"],
    )

    ids_list = results.get("ids", [[]])[0]
    metadatas_list = results.get("metadatas", [[]])[0]
    documents_list = results.get("documents", [[]])[0]
    distances_list = results.get("distances", [[]])[0]

    session = db
    close_session = False
    if session is None:
        from app.database.session import SessionLocal
        session = SessionLocal()
        close_session = True

    valid_hits: List[Dict[str, Any]] = []
    try:
        from app.models.document import Document
        for i in range(len(ids_list)):
            meta = metadatas_list[i]
            doc_id = meta.get("document_id")
            if doc_id is None:
                continue

            doc = session.get(Document, doc_id)
            if doc is None:
                logger.warning("Discarded stale vector %s: document id=%d not found in DB.", ids_list[i], doc_id)
                try:
                    delete_document_vectors(doc_id)
                except Exception as cleanup_err:
                    logger.warning("Failed background cleanup of stale vector %s: %s", ids_list[i], cleanup_err)
                continue

            if not doc.is_active:
                logger.warning("Discarded vector %s: document id=%d is inactive in DB.", ids_list[i], doc_id)
                try:
                    delete_document_vectors(doc_id)
                except Exception as cleanup_err:
                    logger.warning("Failed background cleanup of inactive doc vector %s: %s", ids_list[i], cleanup_err)
                continue

            if supplier_id is not None and doc.supplier_id != supplier_id:
                logger.debug("Filtered out chunk %s: supplier_id mismatch (%s != %s)", ids_list[i], doc.supplier_id, supplier_id)
                continue

            if document_type is not None and doc.document_type != document_type:
                logger.debug("Filtered out chunk %s: document_type mismatch (%s != %s)", ids_list[i], doc.document_type, document_type)
                continue

            hit = {
                "rank": len(valid_hits) + 1,
                "chunk_id": ids_list[i],
                "document_id": doc.id,
                "document_title": doc.title,
                "document_type": doc.document_type,
                "supplier_id": doc.supplier_id,
                "page_number": meta.get("page_number", 1),
                "chunk_index": meta.get("chunk_index", 0),
                "text": documents_list[i],
                "distance": distances_list[i],
                "source_type": "document_ir",
                "authority": "policy_or_sla",
            }
            valid_hits.append(hit)
            if len(valid_hits) >= top_k:
                break

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "Retrieval executed: operation=search, top_k=%d, supplier_id=%s, document_type=%s, candidates_found=%d, valid_hits=%d, duration_ms=%d",
            top_k, supplier_id, document_type, len(ids_list), len(valid_hits), duration_ms
        )
    finally:
        if close_session:
            session.close()

    return valid_hits

