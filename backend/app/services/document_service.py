import hashlib
import logging
import os
import re
import uuid
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.document import (
    Document,
    DocumentType,
    IndexStatus,
    SUPPLIER_REQUIRED_DOC_TYPES,
    GENERAL_POLICY_DOC_TYPES,
)
from app.models.supplier import Supplier
from app.schemas.document import DocumentUpdate

logger = logging.getLogger(__name__)

# PDF Magic bytes signature
PDF_MAGIC_BYTES = b"%PDF-"


class DocumentServiceError(Exception):
    """Base exception for document service errors."""
    pass


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a requested document does not exist."""
    pass


class SupplierNotFoundError(DocumentServiceError):
    """Raised when a linked supplier does not exist."""
    pass


class DocumentValidationError(DocumentServiceError):
    """Raised when document business rules or upload validation fails."""
    pass


class DocumentStorageError(DocumentServiceError):
    """Raised when filesystem reading/writing fails."""
    pass


def get_storage_dir() -> str:
    """
    Returns the absolute path to the configured document storage directory,
    ensuring it exists.
    """
    storage_dir = os.path.abspath(settings.DOCUMENT_STORAGE_DIR)
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def sanitize_original_filename(raw_filename: Optional[str]) -> str:
    """
    Extracts a clean basename from a potentially untrusted client filename.
    Prevents path traversal attempts and preserves safe display names.
    """
    if not raw_filename:
        return "unnamed.pdf"
    # Strip directory components (both / and \)
    base = os.path.basename(raw_filename.replace("\\", "/"))
    # Remove control characters and leading dots
    clean = re.sub(r'[\x00-\x1f\x7f]', '', base).lstrip(".")
    return clean or "document.pdf"


def validate_supplier_document_rules(
    db: Session,
    document_type: str,
    supplier_id: Optional[int],
) -> None:
    """
    Enforces business rules regarding document type and supplier association:
    - supplier_sla, supplier_contract, supplier_performance_report REQUIRE a valid supplier_id.
    - procurement_policy, inventory_replenishment_policy MUST NOT have a supplier_id.
    - other MAY optionally have a supplier_id.
    """
    # 1. Check if supplier is required
    if document_type in SUPPLIER_REQUIRED_DOC_TYPES:
        if not supplier_id:
            raise DocumentValidationError(
                f"Documents of type '{document_type}' must be associated with a valid supplier (supplier_id is required)."
            )
        supplier = db.get(Supplier, supplier_id)
        if not supplier:
            raise SupplierNotFoundError(f"Supplier with ID {supplier_id} not found.")

    # 2. Check if supplier must be omitted for general policies
    elif document_type in GENERAL_POLICY_DOC_TYPES:
        if supplier_id is not None:
            raise DocumentValidationError(
                f"Documents of type '{document_type}' are company-wide policies and cannot be linked to a supplier."
            )

    # 3. Optional supplier for 'other'
    elif document_type == DocumentType.OTHER.value:
        if supplier_id is not None:
            supplier = db.get(Supplier, supplier_id)
            if not supplier:
                raise SupplierNotFoundError(f"Supplier with ID {supplier_id} not found.")
    else:
        # Fallback for unknown document type string
        valid_types = [t.value for t in DocumentType]
        raise DocumentValidationError(
            f"Invalid document type '{document_type}'. Must be one of: {', '.join(valid_types)}"
        )


def get_secure_file_path(storage_key: str) -> str:
    """
    Resolves the filesystem path for a given storage key and verifies
    that no path traversal is possible outside the storage root.
    """
    storage_dir = get_storage_dir()
    # Normalize and ensure basename only
    safe_key = os.path.basename(storage_key)
    target_path = os.path.abspath(os.path.join(storage_dir, safe_key))
    if os.path.commonpath([storage_dir, target_path]) != storage_dir:
        raise DocumentStorageError("Invalid storage key path traversal attempt.")
    return target_path


def create_document(
    db: Session,
    title: str,
    document_type: str,
    file: UploadFile,
    supplier_id: Optional[int] = None,
) -> Document:
    """
    Safely validates, writes, and registers a PDF document:
    1. Validates title, filename, MIME type, size, and PDF magic signature.
    2. Enforces supplier/document-type business rules.
    3. Streams file securely to backend storage with a server-generated UUID.
    4. Computes SHA-256 checksum during writing.
    5. Saves metadata row to database in an atomic transaction.
    6. Cleans up file if database transaction fails.
    """
    clean_title = (title or "").strip()
    if not clean_title:
        raise DocumentValidationError("Document title is required and cannot be blank.")
    if len(clean_title) > 255:
        raise DocumentValidationError("Document title cannot exceed 255 characters.")

    # Validate filename
    raw_filename = file.filename or ""
    if not raw_filename.lower().endswith(".pdf"):
        raise DocumentValidationError("Only PDF documents (.pdf extension) are accepted.")

    # Validate MIME type (if supplied)
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ["application/pdf", "application/x-pdf", "binary/octet-stream"]:
        raise DocumentValidationError(f"Invalid content type '{file.content_type}'. Must be application/pdf.")

    # Validate business rules
    validate_supplier_document_rules(db, document_type, supplier_id)

    # Prepare storage path with random UUID
    storage_dir = get_storage_dir()
    storage_key = f"{uuid.uuid4()}.pdf"
    file_path = get_secure_file_path(storage_key)

    max_bytes = settings.MAX_PDF_UPLOAD_SIZE_MB * 1024 * 1024
    total_bytes = 0
    sha256 = hashlib.sha256()

    file_written = False
    try:
        # Stream file to disk and compute checksum
        with open(file_path, "wb") as dest:
            # Check first chunk for PDF magic bytes
            first_chunk = file.file.read(4096)
            if not first_chunk:
                raise DocumentValidationError("Uploaded PDF file is empty.")

            if not first_chunk.startswith(PDF_MAGIC_BYTES):
                raise DocumentValidationError(
                    "Invalid PDF file header. The file does not contain a valid %PDF- signature."
                )

            dest.write(first_chunk)
            sha256.update(first_chunk)
            total_bytes += len(first_chunk)

            while chunk := file.file.read(65536):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise DocumentValidationError(
                        f"File size exceeds the maximum allowed limit of {settings.MAX_PDF_UPLOAD_SIZE_MB} MB."
                    )
                dest.write(chunk)
                sha256.update(chunk)

        file_written = True

        checksum_hex = sha256.hexdigest()
        original_name = sanitize_original_filename(raw_filename)

        # Create database record
        doc = Document(
            title=clean_title,
            document_type=document_type,
            supplier_id=supplier_id,
            original_filename=original_name,
            storage_key=storage_key,
            mime_type="application/pdf",
            file_size_bytes=total_bytes,
            sha256_checksum=checksum_hex,
            is_active=True,
            index_status=IndexStatus.PENDING.value,
            index_version=getattr(settings, "DOCUMENT_INDEX_VERSION", "v1"),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        logger.info(
            "Document created: id=%d, title=%r, key=%s, size=%d bytes, index_status=%s",
            doc.id, doc.title, doc.storage_key, doc.file_size_bytes, doc.index_status,
        )

        # Automatic indexing after successful persistence
        try:
            from app.services.chroma_service import auto_index_document
            auto_index_document(db=db, document_id=doc.id)
        except Exception as idx_err:
            logger.error(
                "Automatic indexing failed for document id=%d (upload preserved): %s",
                doc.id, idx_err, exc_info=True,
            )
            try:
                from app.services.chroma_service import sanitize_error_message
                doc.index_status = IndexStatus.FAILED.value
                doc.index_error = sanitize_error_message(idx_err)
                db.commit()
            except Exception:
                db.rollback()

        return doc

    except Exception as exc:
        db.rollback()
        # Clean up newly written file if database commit or validation failed
        if file_written and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as cleanup_err:
                logger.warning("Failed to clean up file %s: %s", file_path, cleanup_err)
        if isinstance(exc, DocumentServiceError):
            raise exc
        logger.error("Failed to create document: %s", exc, exc_info=True)
        raise DocumentServiceError(f"Failed to process and store document: {exc}") from exc


def get_document(db: Session, document_id: int) -> Document:
    """
    Retrieves a single document by ID with linked supplier eager-loaded.
    """
    stmt = (
        select(Document)
        .options(joinedload(Document.supplier))
        .where(Document.id == document_id)
    )
    doc = db.scalar(stmt)
    if not doc:
        raise DocumentNotFoundError(f"Document with ID {document_id} not found.")
    return doc


def list_documents(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    document_type: Optional[str] = None,
    supplier_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
) -> List[Document]:
    """
    Lists documents with filtering and search support:
    - document_type exact match
    - supplier_id exact match
    - is_active boolean filter
    - search: case-insensitive title or original_filename matching
    """
    stmt = (
        select(Document)
        .options(joinedload(Document.supplier))
        .order_by(Document.created_at.desc(), Document.id.desc())
    )

    if document_type:
        stmt = stmt.where(Document.document_type == document_type)

    if supplier_id is not None:
        stmt = stmt.where(Document.supplier_id == supplier_id)

    if is_active is not None:
        stmt = stmt.where(Document.is_active == is_active)

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Document.title.ilike(search_pattern),
                Document.original_filename.ilike(search_pattern),
            )
        )

    stmt = stmt.offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def update_document(
    db: Session,
    document_id: int,
    payload: DocumentUpdate,
) -> Document:
    """
    Updates document metadata.
    Revalidates supplier-document type consistency if either field is updated.
    Does NOT allow modifying storage_key, checksum, or file size.
    """
    doc = get_document(db, document_id)

    old_title = doc.title
    old_type = doc.document_type
    old_supplier = doc.supplier_id
    old_active = doc.is_active

    target_type = payload.document_type.value if payload.document_type else doc.document_type
    target_supplier = payload.supplier_id if payload.supplier_id is not None else doc.supplier_id

    # If supplier_id was explicitly provided as None/0 in request, treat as unset
    # We validate the resulting document_type + supplier_id combo
    if payload.document_type is not None or payload.supplier_id is not None:
        validate_supplier_document_rules(db, target_type, target_supplier)
        doc.document_type = target_type
        doc.supplier_id = target_supplier

    if payload.title is not None:
        clean_title = payload.title.strip()
        if not clean_title:
            raise DocumentValidationError("Title cannot be empty.")
        doc.title = clean_title

    if payload.is_active is not None:
        doc.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(doc)
        logger.info("Document updated: id=%d", doc.id)
    except Exception as exc:
        db.rollback()
        raise DocumentServiceError(f"Failed to update document: {exc}") from exc

    # Synchronize Chroma index with metadata changes
    active_changed = (doc.is_active != old_active)
    metadata_changed = (
        doc.title != old_title
        or doc.document_type != old_type
        or doc.supplier_id != old_supplier
    )

    if active_changed and not doc.is_active:
        # If is_active becomes false: remove its vectors from active retrieval
        try:
            from app.services.chroma_service import delete_document_vectors
            delete_document_vectors(document_id=doc.id)
            doc.index_status = IndexStatus.NOT_INDEXED.value
            doc.index_error = None
            db.commit()
            logger.info("Document id=%d deactivated; removed vectors and set not_indexed", doc.id)
        except Exception as exc:
            logger.error("Failed to remove vectors for deactivated document id=%d: %s", doc.id, exc)
    elif (active_changed and doc.is_active) or (metadata_changed and doc.is_active):
        # If is_active becomes true or relevant metadata changed while active: re-index
        try:
            from app.services.chroma_service import auto_index_document
            auto_index_document(db=db, document_id=doc.id)
            logger.info("Document id=%d re-indexed in Chroma after metadata update", doc.id)
        except Exception as exc:
            logger.error("Failed to update Chroma index for document id=%d: %s", doc.id, exc)

    return doc


def delete_document(db: Session, document_id: int) -> None:
    """
    Deletes a document from the database and removes the physical PDF file.
    If the physical file is already missing, gracefully finishes DB deletion.
    Also removes all associated vectors from ChromaDB.
    """
    doc = get_document(db, document_id)
    file_path = get_secure_file_path(doc.storage_key)

    try:
        db.delete(doc)
        db.commit()
        logger.info("Document metadata deleted from DB: id=%d", document_id)
    except Exception as exc:
        db.rollback()
        raise DocumentServiceError(f"Failed to delete document from database: {exc}") from exc

    # Safely remove physical file
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info("Document physical file removed: %s", file_path)
        except OSError as file_err:
            logger.warning("Could not remove physical file %s: %s", file_path, file_err)

    # Safely remove vectors from Chroma
    try:
        from app.services.chroma_service import delete_document_vectors
        delete_document_vectors(document_id=document_id)
        logger.info("Document vectors removed from Chroma: id=%d", document_id)
    except Exception as vec_err:
        logger.error(
            "Failed to delete Chroma vectors for document id=%d (manual re-index cleanup may be required): %s",
            document_id, vec_err, exc_info=True,
        )


def get_document_file_path(doc: Document) -> str:
    """
    Returns the validated absolute path to a document's physical file.
    Raises DocumentStorageError if file does not exist on disk.
    """
    file_path = get_secure_file_path(doc.storage_key)
    if not os.path.exists(file_path):
        raise DocumentNotFoundError(f"Physical file for document {doc.id} is missing from storage.")
    return file_path
