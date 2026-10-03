"""
Supplier Knowledge API Router.
Exposes development and inspection endpoints for the Supplier Knowledge Layer.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.supplier_knowledge import (
    SupplierKnowledgeQueryRequest,
    SupplierKnowledgeQueryResponse,
)
from app.services.supplier_knowledge_service import resolve_supplier_knowledge

router = APIRouter()


@router.post(
    "/query",
    response_model=SupplierKnowledgeQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the unified Supplier Knowledge Layer",
    description=(
        "Analyzes natural language query, performs DB-backed entity resolution, "
        "and routes to structured PostgreSQL facts, grounded ChromaDB evidence, or both. "
        "Does NOT call an LLM or generate prose recommendations."
    ),
)
def query_supplier_knowledge(
    payload: SupplierKnowledgeQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupplierKnowledgeQueryResponse:
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    try:
        result = resolve_supplier_knowledge(
            query=payload.query,
            db=db,
            top_k=payload.top_k,
        )
        return SupplierKnowledgeQueryResponse(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve supplier knowledge.",
        )
