from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.document import Document
from app.services.document_service import get_document, get_document_file_path, list_documents
from app.database.session import get_db
from app.services.document_processing_service import process_document
from app.schemas.document_processing import (
    DocumentChunksListResponse,
    DocumentSearchRequest,
    DocumentSearchResult,
    ReindexResponse,
    DocumentIndexStatusResponse,
    ReconcileIndexResponse,
)
from app.services.chroma_service import (
    index_document_chunks,
    delete_document_vectors,
    auto_index_document,
    rebuild_index,
    reconcile_index_state,
    search_documents,
    get_document_index_status,
)

router = APIRouter()

@router.get(
    "/{document_id}/index-status",
    response_model=DocumentIndexStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document indexing status",
    description="Returns whether the document has vectors indexed in ChromaDB and its chunk count.",
)
def get_index_status_endpoint(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = get_document(db=db, document_id=document_id)
    return get_document_index_status(document_id=doc.id, db=db)

@router.post(
    "/{document_id}/index",
    response_model=DocumentChunksListResponse,
    status_code=status.HTTP_200_OK,
    summary="Index a document's chunks for semantic search",
    description="Extracts text, creates deterministic chunks and upserts them into the ChromaDB collection.",
)
def index_document_endpoint(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = get_document(db=db, document_id=document_id)
    auto_index_document(db=db, document_id=doc.id)
    chunks_response = process_document(db=db, document_id=doc.id)
    return chunks_response

@router.post(
    "/reconcile-index",
    response_model=ReconcileIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Reconcile document index lifecycle with ChromaDB",
    description="Synchronizes PostgreSQL index lifecycle states with actual Chroma vector store contents without rebuilding.",
)
def reconcile_index_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return reconcile_index_state(db=db)

@router.post(
    "/reindex",
    response_model=ReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Rebuild the entire semantic index",
    description="Clears the Chroma collection and re-indexes all active documents.",
)
@router.post(
    "/reindex-all",
    response_model=ReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Rebuild the entire semantic index",
    description="Clears the Chroma collection and re-indexes all active documents.",
)
def reindex_all_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    active_docs = list_documents(db=db, is_active=True)
    summary = rebuild_index(active_documents=active_docs)
    return summary

@router.post(
    "/search",
    response_model=List[DocumentSearchResult],
    status_code=status.HTTP_200_OK,
    summary="Semantic search across indexed document chunks (POST)",
    description="Returns top‑k most similar chunks with metadata. Supports optional filtering by document_type and supplier_id.",
)
def search_post_endpoint(
    payload: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query string cannot be empty.")
    try:
        results = search_documents(
            query=payload.query,
            top_k=payload.top_k,
            document_type=payload.document_type,
            supplier_id=payload.supplier_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return results

@router.get(
    "/search",
    response_model=List[DocumentSearchResult],
    status_code=status.HTTP_200_OK,
    summary="Semantic search across indexed document chunks (GET)",
    description="Returns top‑k most similar chunks with metadata. Supports optional filtering by document_type and supplier_id.",
)
def search_endpoint(
    q: str = Query(..., description="Search query string"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results to return"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query string cannot be empty.")
    try:
        results = search_documents(
            query=q,
            top_k=top_k,
            document_type=document_type,
            supplier_id=supplier_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return results


