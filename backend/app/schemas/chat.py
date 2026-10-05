"""
Pydantic schemas for SmartSupply AI Assistant chat API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ChatConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Optional custom conversation title")


class ChatConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Updated conversation title")


class ChatMessageRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message content",
    )

    @field_validator("message")
    @classmethod
    def validate_message_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or contain only whitespace.")
        return stripped


class ChatSourceItem(BaseModel):
    """
    Provenance tracking for operational PostgreSQL data or Document IR text citations.
    """
    source_type: str = Field(..., description="'postgresql' | 'document_ir'")
    authority: str = Field(..., description="'operational' | 'policy_or_sla'")
    label: Optional[str] = Field(None, description="Human-friendly label e.g. 'ProductSupplier Offer'")
    entity: Optional[str] = Field(None, description="Related entity name e.g. supplier or product")
    document_id: Optional[int] = Field(None, description="Referenced document ID in Document IR")
    document_title: Optional[str] = Field(None, description="Document title")
    document_type: Optional[str] = Field(None, description="Document type e.g. 'supplier_sla', 'procurement_policy'")
    supplier_id: Optional[int] = Field(None, description="Supplier ID if document belongs to supplier")
    page_number: Optional[int] = Field(None, description="Page number of chunk")
    chunk_index: Optional[int] = Field(None, description="Zero-indexed chunk index")
    excerpt: Optional[str] = Field(None, description="Verbatim textual evidence excerpt")
    distance: Optional[float] = Field(None, description="Cosine distance metric from ChromaDB")
    fields: Optional[Dict[str, Any]] = Field(None, description="Structured fields from PostgreSQL")


class ClarificationOption(BaseModel):
    label: str
    value: str


class DecisionSummaryCard(BaseModel):
    """
    Structured replenishment decision details when Decision Agent is invoked.
    """
    product_name: str
    sku: Optional[str] = None
    replenishment_required: bool
    recommended_order_quantity: int
    urgency: str
    required_delivery_window_days: int
    selected_supplier_name: Optional[str] = None
    selected_supplier_id: Optional[int] = None
    unit_cost: Optional[float] = None
    estimated_total_cost: Optional[float] = None
    lead_time_days: Optional[int] = None
    delivery_slack_days: Optional[int] = None
    available_stock: int
    incoming_stock: int
    effective_inventory: int
    reorder_point: int
    predicted_demand: float
    decision_id: Optional[int] = None


class ChatMessageItem(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = Field(None, alias="message_metadata")
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class ChatConversationSummary(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message: Optional[str] = None

    model_config = {
        "from_attributes": True,
    }


class ChatConversationDetail(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageItem] = []

    model_config = {
        "from_attributes": True,
    }


class ChatMessageResponse(BaseModel):
    conversation_id: int
    message_id: int
    status: str = Field("success", description="'success' | 'degraded' | 'clarification_needed'")
    answer: str
    intent: str
    resolved_entities: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs_used: List[str] = Field(default_factory=list)
    sources: List[ChatSourceItem] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None
    clarification_options: Optional[List[ClarificationOption]] = None
    decision_summary: Optional[DecisionSummaryCard] = None
    decision_details: Optional[Dict[str, Any]] = None
    inventory_snapshot: Optional[Dict[str, Any]] = None
    forecast_summary: Optional[Dict[str, Any]] = None
    stockout_summary: Optional[Dict[str, Any]] = None
    supplier_offer: Optional[Dict[str, Any]] = None
    forecast_horizon_days: Optional[int] = None
    created_at: datetime
