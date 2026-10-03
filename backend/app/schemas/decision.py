"""
Pydantic Schemas for Member 4: Replenishment Decision Agent.
Defines input requests, output recommendation payloads, human approval schemas,
and context models adhering strictly to Pydantic v2 conventions.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.decision import ApprovalStatus


class DecisionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionRecommendationRequest(BaseModel):
    """
    Payload for requesting a comprehensive replenishment decision and supplier selection.
    Accepts product_id or SKU with optional horizon and urgency controls.
    """
    product_id: Optional[int] = Field(None, gt=0, description="Product catalog ID to analyze (must be > 0)")
    sku: Optional[str] = Field(None, description="Optional product SKU code")
    forecast_horizon_days: int = Field(
        default=14,
        gt=0,
        le=90,
        description="Forecast horizon in days (default: 14)",
    )
    lead_time_days: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional lead time in days. If omitted, inferred from supplier terms or default.",
    )
    urgency: str = Field(
        default="normal",
        description="Procurement urgency: normal | high | emergency",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "product_id": 1,
                "forecast_horizon_days": 14,
                "urgency": "normal",
            }
        },
    )

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        valid = {"normal", "high", "emergency"}
        norm = (v or "").strip().lower()
        return norm if norm in valid else "normal"


class DecisionApprovalRequest(BaseModel):
    """
    Payload for recording human manager approval or rejection.
    """
    status: ApprovalStatus = Field(
        ...,
        description="Action status: APPROVED or REJECTED",
    )
    reviewer_notes: Optional[str] = Field(
        None,
        description="Optional commentary or procurement approval notes",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Required or optional reason explaining why recommendation was rejected",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "status": "APPROVED",
                "reviewer_notes": "Approved for immediate PO generation.",
            }
        },
    )


class SelectedSupplierInfo(BaseModel):
    """
    Authoritative details of the supplier selected for the recommended replenishment order.
    """
    supplier_id: int = Field(..., description="PostgreSQL supplier primary key")
    supplier_code: Optional[str] = Field(None, description="Supplier code")
    supplier_name: str = Field(..., description="Supplier company name")
    unit_cost: float = Field(..., description="Authoritative wholesale unit cost")
    moq: int = Field(..., description="Supplier minimum order quantity")
    lead_time_days: int = Field(..., description="Delivery lead time in days")
    estimated_total_cost: float = Field(..., description="unit_cost * recommended_order_quantity")
    selection_reason: str = Field(..., description="Justification for selecting this supplier candidate")

    model_config = ConfigDict(
        from_attributes=True,
    )


class InventorySnapshot(BaseModel):
    """
    Snapshot of inventory monitoring agent output consumed in this decision.
    """
    product_id: int
    product_name: str
    sku: Optional[str] = None
    on_hand: int
    reserved: int
    incoming: int
    available_stock: int
    reorder_point: int
    status: str

    model_config = ConfigDict(
        from_attributes=True,
    )


class DemandSnapshot(BaseModel):
    """
    Snapshot of demand & risk agent output consumed in this decision.
    """
    product_id: int
    forecast_horizon_days: int
    total_forecasted_demand: float
    lead_time_days: int
    expected_demand_over_lead_time: float
    risk_level: str
    projected_stockout_date: Optional[date] = None
    selected_model: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class SupplierCandidateOption(BaseModel):
    """
    Candidate supplier option evaluated during decision synthesis.
    """
    supplier_id: int
    supplier_code: Optional[str] = None
    supplier_name: str
    unit_cost: float
    moq: int
    lead_time_days: int
    meets_moq: Optional[bool] = None
    estimated_cost: Optional[float] = None
    advantages: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        from_attributes=True,
    )


class DecisionRecommendationResponse(BaseModel):
    """
    Comprehensive, explainable decision support payload delivered by Member 4.
    """
    id: Optional[int] = Field(None, description="Persisted decision record ID if stored")
    product_id: int = Field(..., description="Product catalog ID")
    sku: Optional[str] = Field(None, description="Product SKU code")
    product_name: str = Field(..., description="Product catalog name")

    # Three core outputs
    replenishment_required: bool = Field(
        ...,
        description="Authoritative determination whether inventory reorder is required (YES / NO)",
    )
    recommended_order_quantity: int = Field(
        ...,
        ge=0,
        description="Deterministic recommended order quantity (strictly >= 0)",
    )
    selected_supplier: Optional[SelectedSupplierInfo] = Field(
        None,
        description="Selected supplier meeting operational criteria and procurement policy",
    )

    # Synthesis & Explainability
    risk_level: str = Field(..., description="Aggregated risk level: LOW | MEDIUM | HIGH | CRITICAL")
    reasoning: str = Field(..., description="Concise explainable rationale synthesized by Grok / deterministic engine")
    factors: List[str] = Field(default_factory=list, description="Key operational factors considered")
    warnings: List[str] = Field(default_factory=list, description="Operational caveats or missing-data warnings")
    policy_references: List[str] = Field(default_factory=list, description="Procurement/inventory corporate policies applied")
    confidence: Optional[float] = Field(None, description="Statistical or synthesis confidence metric where meaningful")

    # Human-in-the-loop Governance
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="Governance status: PENDING | APPROVED | REJECTED",
    )
    reviewed_by: Optional[int] = Field(None, description="User ID of manager who approved/rejected")
    reviewed_at: Optional[datetime] = Field(None, description="Timestamp of human review")
    reviewer_notes: Optional[str] = Field(None, description="Human review notes")
    rejection_reason: Optional[str] = Field(None, description="Rejection rationale if rejected")
    created_at: Optional[datetime] = Field(None, description="Recommendation creation timestamp")

    # Source context snapshots for audit and frontend inspection
    inventory_context: Optional[InventorySnapshot] = Field(None, description="Inventory Agent input context")
    demand_context: Optional[DemandSnapshot] = Field(None, description="Demand Agent input context")
    supplier_options: List[SupplierCandidateOption] = Field(
        default_factory=list,
        description="All evaluated supplier candidates from Supplier Agent",
    )

    model_config = ConfigDict(
        from_attributes=True,
    )


class DecisionListResponse(BaseModel):
    """
    Paginated list of decision records.
    """
    items: List[DecisionRecommendationResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of records matching query")

    model_config = ConfigDict(
        from_attributes=True,
    )
