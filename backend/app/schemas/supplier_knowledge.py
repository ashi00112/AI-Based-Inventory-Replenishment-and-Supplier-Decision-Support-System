"""
Pydantic schemas for the Supplier Knowledge Layer.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document_processing import DocumentSearchResult


class QueryAnalysisResponse(BaseModel):
    """
    Structured query understanding result with intent, route, and resolved entities.
    """
    original_query: str
    normalized_query: str
    intent: str = Field(..., description="Classified intent (e.g., supplier_terms, supplier_policy, mixed_supplier_decision)")
    route: str = Field(..., description="Target knowledge route: structured | document | mixed | unknown")
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    supplier_code: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    sku: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    unresolved_terms: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SupplierKnowledgeQueryRequest(BaseModel):
    """
    Request model for the unified supplier knowledge endpoint.
    """
    query: str = Field(..., min_length=1, description="Natural language supplier query")
    top_k: int = Field(5, ge=1, le=20, description="Max document chunks to retrieve if routed to documents")

    model_config = ConfigDict(from_attributes=True)


class SupplierKnowledgeQueryResponse(BaseModel):
    """
    Unified knowledge response combining query analysis, structured facts, and document evidence.
    """
    query_analysis: QueryAnalysisResponse
    structured_facts: List[Dict[str, Any]] = Field(default_factory=list)
    document_evidence: List[DocumentSearchResult] = Field(default_factory=list)
    needs_clarification: bool = Field(False, description="Flag indicating if the query intent was unclear and requires user clarification")
    clarification_reason: Optional[str] = Field(None, description="Deterministic explanation for clarification if query was unknown")

    model_config = ConfigDict(from_attributes=True)
