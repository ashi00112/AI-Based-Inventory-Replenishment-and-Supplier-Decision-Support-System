"""
Pydantic schemas for Document Text Extraction and Chunking.
"""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PageExtractionResult(BaseModel):
    """
    Extracted text and metadata for a single document page.
    """
    document_id: int = Field(..., description="ID of the parent Document record")
    page_number: int = Field(..., ge=1, description="1-based page number")
    extracted_text: str = Field(..., description="Normalized text content extracted from page")
    char_count: int = Field(..., ge=0, description="Character count of extracted text")

    model_config = ConfigDict(from_attributes=True)


class DocumentExtractionResponse(BaseModel):
    """
    Page-by-page extraction output for an entire document.
    """
    document_id: int
    document_title: str
    document_type: str
    supplier_id: Optional[int] = None
    total_pages: int
    total_char_count: int
    pages: List[PageExtractionResult]

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkResponse(BaseModel):
    """
    Deterministic chunk representation preserving source provenance.
    """
    chunk_id: str = Field(..., description="Unique deterministic identifier for the chunk")
    document_id: int
    document_title: str
    document_type: str
    supplier_id: Optional[int] = None
    page_number: int = Field(..., description="1-based source page number")
    start_page: int = Field(..., description="Starting page of chunk provenance")
    end_page: int = Field(..., description="Ending page of chunk provenance")
    chunk_index: int = Field(..., ge=0, description="Sequential 0-based chunk index")
    text: str = Field(..., description="Chunk text content")
    char_count: int = Field(..., ge=1, description="Character count of chunk text")

    model_config = ConfigDict(from_attributes=True)


class DocumentChunksListResponse(BaseModel):
    """
    Container response listing all deterministic chunks for a document.
    """
    document_id: int
    document_title: str
    total_chunks: int
    chunk_size: int
    overlap: int
    chunks: List[DocumentChunkResponse]

    model_config = ConfigDict(from_attributes=True)


class DocumentSearchRequest(BaseModel):
    """
    Request payload for semantic document search.
    """
    query: str = Field(..., min_length=1, description="Semantic search query text")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of chunks to return")
    document_type: Optional[str] = Field(None, description="Optional document type filter")
    supplier_id: Optional[int] = Field(None, description="Optional supplier ID filter")

    model_config = ConfigDict(from_attributes=True)


class DocumentSearchResult(BaseModel):
    """
    Single retrieved chunk result with similarity distance and provenance.
    """
    rank: Optional[int] = None
    chunk_id: Optional[str] = None
    document_id: int
    document_title: str
    title: Optional[str] = None
    document_type: Optional[str] = None
    supplier_id: Optional[int] = None
    page_number: int = Field(1, description="1-based source page number")
    chunk_index: int = Field(0, description="Sequential 0-based chunk index")
    text: str
    distance: float = 0.0
    source_type: str = "document_ir"
    authority: str = "policy_or_sla"

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def sync_titles(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t = data.get("document_title") or data.get("title") or "Untitled Document"
            data.setdefault("document_title", t)
            data.setdefault("title", t)
        return data

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class ReindexResponse(BaseModel):
    """
    Summary response after rebuilding semantic index.
    """
    documents_indexed: int
    chunks_indexed: int

    model_config = ConfigDict(from_attributes=True)


class DocumentIndexStatusResponse(BaseModel):
    """
    Lightweight index status representation for a document.
    """
    document_id: int
    indexed: bool
    chunk_count: int
    index_status: Optional[str] = "not_indexed"
    last_indexed_at: Optional[Any] = None
    index_version: Optional[str] = None
    index_error: Optional[str] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReconcileIndexResponse(BaseModel):
    """
    Summary response after reconciling PostgreSQL document lifecycle state against ChromaDB.
    """
    total_documents_checked: int
    reconciled_count: int
    active_indexed: int
    active_unindexed: int
    inactive_vectors_removed: int
    stale_vectors_purged: int
    missing_source_count: int = 0
    reindexed_count: int = 0

    model_config = ConfigDict(from_attributes=True)



