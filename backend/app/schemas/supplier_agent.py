"""
Pydantic Schemas for Member 3: Supplier / Procurement Agent.
Defines strict input and output contracts for supplier assessment and Member 4 handoff.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.document_processing import DocumentSearchResult


class SupplierAgentRequest(BaseModel):
    """Input request contract for the Supplier / Procurement Agent."""
    product_id: Optional[int] = Field(None, description="Optional catalog product ID")
    sku: Optional[str] = Field(None, description="Optional product SKU (e.g. DEMO-001)")
    product_name: Optional[str] = Field(None, description="Optional product name (e.g. 'Wireless Mouse')")
    requested_quantity: Optional[int] = Field(None, description="Input quantity supplied by caller; NOT calculated by agent")
    urgency: str = Field("normal", description="Procurement urgency: normal | high | emergency")
    stockout_risk: Optional[str] = Field(None, description="Current stockout risk level (e.g. low, medium, high)")
    supplier_id: Optional[int] = Field(None, description="Optional preferred or filter supplier ID")
    query: Optional[str] = Field(None, description="Optional natural language query from caller")

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        valid_urgencies = {"normal", "high", "emergency"}
        norm = (v or "").strip().lower()
        if norm not in valid_urgencies:
            return "normal"
        return norm

    @field_validator("requested_quantity")
    @classmethod
    def validate_requested_quantity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("requested_quantity must be greater than 0 if provided.")
        return v


class CandidateAssessment(BaseModel):
    """Grounded assessment of a single supplier candidate."""
    supplier_id: int = Field(..., description="PostgreSQL supplier primary key")
    supplier_code: Optional[str] = Field(None, description="Authoritative supplier code")
    supplier_name: str = Field(..., description="Authoritative supplier name")
    unit_cost: float = Field(..., description="Authoritative unit cost from PostgreSQL ProductSupplier")
    moq: int = Field(..., description="Authoritative minimum order quantity from PostgreSQL")
    lead_time_days: int = Field(..., description="Authoritative lead time in days from PostgreSQL")
    meets_moq: Optional[bool] = Field(None, description="True if requested_quantity >= moq; None if quantity omitted")
    estimated_cost: Optional[float] = Field(None, description="Estimated total cost (unit_cost * requested_quantity)")
    advantages: List[str] = Field(default_factory=list, description="Specific trade-off advantages grounded in facts/policy")
    risks: List[str] = Field(default_factory=list, description="Specific trade-off risks or SLA considerations")
    evidence: List[DocumentSearchResult] = Field(default_factory=list, description="Grounded document evidence chunks supporting assessment")


class AdvisorySupplier(BaseModel):
    """Member 3 advisory preferred supplier recommendation."""
    supplier_id: int = Field(..., description="Recommended supplier ID matching one of the active candidates")
    supplier_name: str = Field(..., description="Authoritative supplier name matching PostgreSQL")
    reason: str = Field(..., description="Grounded procurement rationale explaining recommendation")


class SupplierAgentResponse(BaseModel):
    """
    Structured output contract for the Supplier / Procurement Agent.
    Serves as the Member 4 handoff contract.
    """
    agent: str = Field("supplier_procurement", description="Identifier of the executing agent")
    status: str = Field("success", description="Execution status: success | degraded | clarification_needed | error")
    product: Optional[Dict[str, Any]] = Field(None, description="Authoritative resolved product metadata")
    requested_quantity: Optional[int] = Field(None, description="The input quantity requested by caller (never altered)")
    urgency: str = Field("normal", description="Procurement urgency passed to the agent")
    candidate_assessments: List[CandidateAssessment] = Field(default_factory=list, description="Evaluated supplier options")
    advisory_supplier: Optional[AdvisorySupplier] = Field(None, description="Advisory supplier recommendation (advisory only)")
    policy_constraints: List[str] = Field(default_factory=list, description="Applicable corporate procurement/inventory policy rules")
    warnings: List[str] = Field(default_factory=list, description="Operational warnings or caveat notices")
    needs_clarification: bool = Field(False, description="Flag indicating caller clarification is needed")
    clarification_prompt: Optional[str] = Field(None, description="Specific question for caller if entity is ambiguous")
    advisory_only: bool = Field(True, description="Strict declaration that Member 3 recommendation is advisory only")
