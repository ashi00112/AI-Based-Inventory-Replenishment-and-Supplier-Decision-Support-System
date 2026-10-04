"""
Pydantic Schemas for Member 4: Replenishment Decision Agent.
Defines input requests, output recommendation payloads, human approval schemas,
situation-aware candidate scoring, grounded SLA policy signals, and context models.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.decision import ApprovalStatus
from app.schemas.document_processing import DocumentSearchResult


class DecisionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UrgencyLevel(str, Enum):
    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"


class ScoreBreakdown(BaseModel):
    """
    Transparent numeric score breakdown for a supplier candidate across three core dimensions.
    """
    cost_score: float = Field(..., ge=0.0, le=100.0, description="Normalized cost efficiency score (0-100)")
    delivery_score: float = Field(..., ge=0.0, le=100.0, description="Delivery suitability and safety margin score (0-100)")
    sla_score: float = Field(..., ge=0.0, le=100.0, description="SLA reliability and contractual suitability score (0-100)")
    weighted_score: float = Field(..., ge=0.0, le=100.0, description="Composite weighted decision score (0-100)")

    model_config = ConfigDict(extra="forbid")


class SupplierPolicySignals(BaseModel):
    """
    Structured, grounded decision signals derived from retrieved procurement policy and supplier SLA documents.
    Every signal must have supporting retrieved document evidence.
    """
    compliance_status: str = Field(
        default="eligible",
        description="Supplier compliance status: eligible | restricted | suspended | unknown",
    )
    expedited_support: str = Field(
        default="unknown",
        description="Expedited order support: strong | supported | limited | not_supported | unknown",
    )
    reliability_score: Optional[float] = Field(
        default=None,
        description="Observed numeric reliability percentage if explicitly grounded in performance reports",
    )
    otif_target: Optional[float] = Field(
        default=None,
        description="Contractual OTIF target percentage if explicitly present in evidence",
    )
    high_risk_suitability: str = Field(
        default="unknown",
        description="Suitability for high-risk procurement: preferred | acceptable | limited | unknown",
    )
    emergency_suitability: str = Field(
        default="unknown",
        description="Suitability for emergency replenishment: preferred | acceptable | limited | not_supported | unknown",
    )
    bulk_suitability: str = Field(
        default="unknown",
        description="Suitability for standard bulk replenishment: preferred | acceptable | unknown",
    )
    delay_risk: str = Field(
        default="unknown",
        description="Historical delay variance risk: low | medium | high | unknown",
    )
    evidence_refs: List[int] = Field(
        default_factory=list,
        description="Document IDs from which signals were grounded",
    )

    model_config = ConfigDict(extra="forbid")


class DetectedProcurementCondition(BaseModel):
    """
    Structured summary of the automatically derived procurement condition.
    """
    stockout_risk: str = Field(..., description="Stockout risk category: LOW | MEDIUM | HIGH | CRITICAL")
    procurement_urgency: str = Field(..., description="System-derived procurement urgency: normal | high | emergency")
    effective_urgency: str = Field(..., description="Effective urgency applied after optional manual override")
    manual_override_applied: bool = Field(default=False, description="True if manual override was supplied and used")
    required_delivery_window_days: int = Field(..., description="Maximum acceptable lead time before unsafe stock breach")
    days_until_buffer_breach: Optional[int] = Field(None, description="Days until projected inventory drops below ROP buffer")
    days_until_unsafe: Optional[int] = Field(None, description="Alias for days_until_buffer_breach for backward compatibility")
    days_until_stockout: Optional[int] = Field(None, description="Days until available-to-fulfil inventory reaches zero")
    reason: str = Field(..., description="Clear explanation grounded in stockout timing and supplier capabilities")

    # UI compatibility aliases
    risk_level: Optional[str] = None
    derived_urgency: Optional[str] = None
    condition_reason: Optional[str] = None
    weight_cost: Optional[float] = 0.15
    weight_delivery: Optional[float] = 0.60
    weight_sla: Optional[float] = 0.25
    governing_policy_doc: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class DecisionRecommendationRequest(BaseModel):
    """
    Payload for requesting a comprehensive replenishment decision and supplier selection.
    Accepts product_id or SKU with optional horizon and optional manual urgency override.
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
    urgency_override: Optional[str] = Field(
        default=None,
        description="Optional manual procurement urgency override: normal | high | emergency. If None, derived automatically.",
    )
    urgency: Optional[str] = Field(
        default=None,
        description="Backwards-compatible urgency field. Treated as urgency_override if specified and not 'auto'.",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "product_id": 1,
                "forecast_horizon_days": 14,
            }
        },
    )

    @field_validator("urgency_override", "urgency")
    @classmethod
    def validate_urgency_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        norm = v.strip().lower()
        if norm in ("auto", "none", ""):
            return None
        if norm in ("normal", "high", "emergency"):
            return norm
        return "normal"


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
    advantages: List[str] = Field(
        default_factory=list,
        description="Key advantages of selected supplier",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Known operational risks of selected supplier",
    )
    evidence: List[DocumentSearchResult] = Field(
        default_factory=list,
        description="Grounded document evidence chunks supporting this supplier",
    )
    delivery_slack_days: Optional[int] = Field(
        default=None,
        description="Delivery slack in days (required_delivery_window - supplier.lead_time_days)",
    )
    eligibility_status: Optional[str] = Field(
        default="eligible",
        description="Supplier eligibility state: eligible | zero_slack | infeasible | policy_restricted",
    )
    eligibility_reason: Optional[str] = Field(
        default=None,
        description="Explanation for eligibility determination",
    )
    score_breakdown: Optional[ScoreBreakdown] = Field(
        default=None,
        description="Detailed score breakdown (Cost, Delivery, SLA, Weighted)",
    )
    policy_signals: Optional[SupplierPolicySignals] = Field(
        default=None,
        description="Structured document-derived SLA and policy signals",
    )

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
    effective_inventory: Optional[int] = Field(
        None,
        description="Effective inventory position (available_stock + incoming)",
    )
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
    evidence: List[DocumentSearchResult] = Field(
        default_factory=list,
        description="Grounded document evidence chunks supporting candidate assessment",
    )
    delivery_slack_days: Optional[int] = Field(
        default=None,
        description="Delivery slack in days (required_delivery_window - supplier.lead_time_days)",
    )
    is_feasible: Optional[bool] = Field(
        default=True,
        description="True if candidate lead time is within required delivery window and supplier is compliant",
    )
    disqualification_reason: Optional[str] = Field(
        default=None,
        description="Explanation if candidate is disqualified due to infeasibility or policy restriction",
    )
    eligibility_status: Optional[str] = Field(
        default="eligible",
        description="Supplier eligibility state: eligible | zero_slack | infeasible | policy_restricted",
    )
    eligibility_reason: Optional[str] = Field(
        default=None,
        description="Explanation for eligibility determination",
    )
    cost_score: Optional[float] = Field(default=None, description="Cost score (0-100)")
    delivery_score: Optional[float] = Field(default=None, description="Delivery score (0-100)")
    sla_score: Optional[float] = Field(default=None, description="SLA score (0-100)")
    weighted_score: Optional[float] = Field(default=None, description="Weighted composite score (0-100)")
    score_breakdown: Optional[ScoreBreakdown] = Field(default=None, description="Nested score breakdown")
    policy_signals: Optional[SupplierPolicySignals] = Field(default=None, description="Structured SLA signals")
    score: Optional[float] = Field(default=None, description="Normalized total score (0-1.0 or 0-100)")
    signals: Optional[Any] = Field(default=None, description="Compatibility alias for policy_signals")

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
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

    # Automatic Urgency & Timing metrics
    derived_urgency: Optional[str] = Field(None, description="System-derived urgency: normal | high | emergency")
    effective_urgency: Optional[str] = Field(None, description="Effective urgency applied")
    manual_urgency_override: Optional[str] = Field(None, description="Manual urgency override if provided")
    manual_override_applied: bool = Field(default=False, description="Whether manual override was used")
    required_delivery_window_days: Optional[int] = Field(None, description="Required delivery window in days")
    days_until_buffer_breach: Optional[int] = Field(None, description="Days until projected inventory breaches ROP buffer")
    days_until_unsafe: Optional[int] = Field(None, description="Alias for days_until_buffer_breach for backward compatibility")
    days_until_stockout: Optional[int] = Field(None, description="Days until available-to-fulfil inventory reaches zero")
    detected_condition: Optional[DetectedProcurementCondition] = Field(None, description="Structured detected procurement condition")

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
