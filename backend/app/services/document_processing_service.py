"""
Document Processing Service for SmartSupply Electronics.

Provides deterministic page-by-page text extraction and paragraph-aware chunking
for stored PDF documents using PyMuPDF (fitz), with source page provenance.
"""

import logging
import os
import re
from typing import List, Optional
import pymupdf
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document_processing import (
    PageExtractionResult,
    DocumentExtractionResponse,
    DocumentChunkResponse,
    DocumentChunksListResponse,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentStorageError,
    get_document,
    get_document_file_path,
)

logger = logging.getLogger(__name__)

# Configurable Default Chunking Parameters
DEFAULT_CHUNK_SIZE: int = 1000       # Target characters per chunk (approx. 800–1200)
DEFAULT_CHUNK_OVERLAP: int = 180     # Target character overlap between consecutive chunks (approx. 150–200)


class DocumentProcessingError(Exception):
    """Base domain exception for document processing operations."""
    pass


class CorruptedPDFError(DocumentProcessingError):
    """Raised when a PDF file is corrupt, malformed, or has an invalid structure."""
    pass


class EncryptedPDFError(DocumentProcessingError):
    """Raised when a PDF document is encrypted or password protected."""
    pass


class EmptyDocumentError(DocumentProcessingError):
    """Raised when a PDF file contains 0 readable pages."""
    pass


def normalize_text(text: Optional[str]) -> str:
    """
    Performs conservative text cleaning on extracted PDF text:
    - Normalizes carriage returns and newlines to '\\n'
    - Replaces non-breaking spaces and Unicode horizontal whitespace with standard space
    - Strips trailing whitespace from each line
    - Collapses consecutive spaces/tabs within lines into a single space
    - Collapses 3 or more consecutive newlines into 2 ('\\n\\n') to preserve paragraph structure
    - Trims leading and trailing whitespace of the overall text

    Preserves:
    - Exact vocabulary, punctuation, capitalization, acronyms, and legal/commercial clauses.
    """
    if not text:
        return ""

    # 1. Normalize line endings
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Normalize non-breaking and special spaces to standard space
    cleaned = cleaned.replace("\xa0", " ").replace("\u200b", "")

    # 3. Clean line by line: collapse horizontal whitespace, strip line ends
    lines = []
    for line in cleaned.split("\n"):
        # Collapse multiple horizontal spaces/tabs
        normalized_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(normalized_line)

    reconstructed = "\n".join(lines)

    # 4. Collapse excessive consecutive blank lines (3+ newlines -> 2 newlines)
    reconstructed = re.sub(r"\n{3,}", "\n\n", reconstructed)

    # 5. Trim leading and trailing whitespace
    return reconstructed.strip()


def extract_text_from_pdf_bytes(
    pdf_bytes: bytes,
    document_id: int = 0,
) -> List[PageExtractionResult]:
    """
    Extracts text page-by-page from raw PDF bytes using PyMuPDF.

    Returns:
    - List of PageExtractionResult with 1-based page numbers.

    Raises:
    - CorruptedPDFError: if bytes cannot be parsed as a valid PDF.
    - EncryptedPDFError: if the document is password-protected.
    """
    if not pdf_bytes:
        raise CorruptedPDFError("PDF binary payload is empty.")

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.error("PyMuPDF failed to open PDF document: %s", exc)
        raise CorruptedPDFError(f"Failed to parse PDF binary: {exc}") from exc

    try:
        if doc.is_encrypted:
            raise EncryptedPDFError("Document is encrypted and requires an access password.")

        if len(doc) == 0:
            raise CorruptedPDFError("PDF document contains 0 pages.")

        page_results: List[PageExtractionResult] = []

        for page_idx in range(len(doc)):
            page_num = page_idx + 1  # 1-based page index
            try:
                page = doc.load_page(page_idx)
                raw_text = page.get_text("text") or ""
            except Exception as page_exc:
                logger.warning("Error reading page %d for doc %d: %s", page_num, document_id, page_exc)
                raw_text = ""

            clean_text = normalize_text(raw_text)
            page_results.append(
                PageExtractionResult(
                    document_id=document_id,
                    page_number=page_num,
                    extracted_text=clean_text,
                    char_count=len(clean_text),
                )
            )

        return page_results

    finally:
        doc.close()


def extract_document_text(db: Session, document_id: int) -> DocumentExtractionResponse:
    """
    Retrieves a stored Document by ID and extracts text page-by-page.
    Validates document existence and storage integrity.
    """
    doc = get_document(db, document_id)
    file_path = get_document_file_path(doc)

    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
    except OSError as io_err:
        logger.error("Failed to read document file %s: %s", file_path, io_err)
        raise DocumentStorageError(f"Could not read physical file for document {document_id}: {io_err}") from io_err

    pages = extract_text_from_pdf_bytes(pdf_bytes=pdf_bytes, document_id=doc.id)
    total_char_count = sum(p.char_count for p in pages)

    return DocumentExtractionResponse(
        document_id=doc.id,
        document_title=doc.title,
        document_type=doc.document_type,
        supplier_id=doc.supplier_id,
        total_pages=len(pages),
        total_char_count=total_char_count,
        pages=pages,
    )


def _split_long_paragraph(paragraph: str, max_size: int, overlap: int) -> List[str]:
    """
    Breaks a single oversized paragraph into smaller cohesive units.
    Splits first on sentence boundaries, then falls back to character windows if needed.
    """
    if len(paragraph) <= max_size:
        return [paragraph]

    # Try sentence splitting
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
    if not sentences:
        sentences = [paragraph]

    units: List[str] = []
    current_sentence_group: List[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)
        if sent_len > max_size:
            # If current group has content, flush it
            if current_sentence_group:
                units.append(" ".join(current_sentence_group))
                current_sentence_group = []
                current_len = 0

            # Split huge sentence into character slices
            step = max_size - overlap if max_size > overlap else max_size
            for i in range(0, len(sent), step):
                slice_chunk = sent[i : i + max_size].strip()
                if slice_chunk:
                    units.append(slice_chunk)
            continue

        added = sent_len + (1 if current_sentence_group else 0)
        if current_len + added <= max_size:
            current_sentence_group.append(sent)
            current_len += added
        else:
            if current_sentence_group:
                units.append(" ".join(current_sentence_group))
            current_sentence_group = [sent]
            current_len = sent_len

    if current_sentence_group:
        units.append(" ".join(current_sentence_group))

    return units


def chunk_document_text(
    extraction: DocumentExtractionResponse,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[DocumentChunkResponse]:
    """
    Deterministically segments extracted document pages into paragraph-aware chunks.

    Guarantees:
    - Page-local provenance: chunks belong to exactly one source page (page_number = start_page = end_page).
    - Paragraph awareness: keeps paragraphs intact whenever they fit within chunk_size.
    - Deterministic output: identical input text yields identical chunks and indices.
    - Source metadata: every chunk retains document_id, title, type, supplier_id, and 1-based page.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size})")

    all_chunks: List[DocumentChunkResponse] = []
    global_chunk_idx = 0

    for page in extraction.pages:
        page_text = page.extracted_text
        if not page_text:
            continue

        # Split into distinct paragraphs on double newlines
        raw_paragraphs = [p.strip() for p in re.split(r"\n\n+", page_text) if p.strip()]
        if not raw_paragraphs:
            continue

        # Flatten into paragraph-sized units (splitting oversized paragraphs if necessary)
        units: List[str] = []
        for para in raw_paragraphs:
            units.extend(_split_long_paragraph(para, max_size=chunk_size, overlap=overlap))

        # Accumulate units into chunks with paragraph-aware overlap
        current_pieces: List[str] = []
        current_len = 0

        for unit in units:
            unit_len = len(unit)
            added_len = unit_len + (2 if current_pieces else 0)  # accounted with \n\n separator

            if (current_len + added_len <= chunk_size) or not current_pieces:
                current_pieces.append(unit)
                current_len += added_len
            else:
                # Emit current accumulated chunk
                chunk_str = "\n\n".join(current_pieces).strip()
                if chunk_str:
                    all_chunks.append(
                        DocumentChunkResponse(
                            chunk_id=f"doc-{extraction.document_id}-p{page.page_number}-c{global_chunk_idx}",
                            document_id=extraction.document_id,
                            document_title=extraction.document_title,
                            document_type=extraction.document_type,
                            supplier_id=extraction.supplier_id,
                            page_number=page.page_number,
                            start_page=page.page_number,
                            end_page=page.page_number,
                            chunk_index=global_chunk_idx,
                            text=chunk_str,
                            char_count=len(chunk_str),
                        )
                    )
                    global_chunk_idx += 1

                # Calculate overlap context for next chunk
                overlap_pieces: List[str] = []
                overlap_len = 0
                for piece in reversed(current_pieces):
                    piece_cost = len(piece) + (2 if overlap_pieces else 0)
                    if overlap_len + piece_cost <= overlap:
                        overlap_pieces.insert(0, piece)
                        overlap_len += piece_cost
                    else:
                        break

                # If no full paragraph piece fit into overlap, take trailing text of last piece
                if not overlap_pieces and overlap > 0 and current_pieces:
                    tail = current_pieces[-1]
                    if len(tail) > overlap:
                        slice_point = len(tail) - overlap
                        # Find word boundary after slice point
                        space_idx = tail.find(" ", slice_point)
                        if space_idx != -1 and space_idx < len(tail) - 1:
                            overlap_text = tail[space_idx + 1 :]
                        else:
                            overlap_text = tail[slice_point:]
                        if overlap_text:
                            overlap_pieces = [overlap_text]
                    else:
                        overlap_pieces = [tail]

                # Start next accumulator with overlap context + current unit
                current_pieces = list(overlap_pieces)
                current_pieces.append(unit)
                current_len = sum(len(p) for p in current_pieces) + (2 * max(0, len(current_pieces) - 1))

        # Emit trailing chunk for the page
        if current_pieces:
            chunk_str = "\n\n".join(current_pieces).strip()
            if chunk_str:
                all_chunks.append(
                    DocumentChunkResponse(
                        chunk_id=f"doc-{extraction.document_id}-p{page.page_number}-c{global_chunk_idx}",
                        document_id=extraction.document_id,
                        document_title=extraction.document_title,
                        document_type=extraction.document_type,
                        supplier_id=extraction.supplier_id,
                        page_number=page.page_number,
                        start_page=page.page_number,
                        end_page=page.page_number,
                        chunk_index=global_chunk_idx,
                        text=chunk_str,
                        char_count=len(chunk_str),
                    )
                )
                global_chunk_idx += 1

    return all_chunks


def process_document(
    db: Session,
    document_id: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> DocumentChunksListResponse:
    """
    High-level orchestrator: extracts text page-by-page and produces deterministic chunks.
    """
    extraction = extract_document_text(db=db, document_id=document_id)
    chunks = chunk_document_text(extraction=extraction, chunk_size=chunk_size, overlap=overlap)

    return DocumentChunksListResponse(
        document_id=extraction.document_id,
        document_title=extraction.document_title,
        total_chunks=len(chunks),
        chunk_size=chunk_size,
        overlap=overlap,
        chunks=chunks,
    )
