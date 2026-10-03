import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin


class ApprovalStatus(str, enum.Enum):
    """
    Workflow approval states for decision recommendations.
    Enforces human-in-the-loop oversight before purchase execution.
    """
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DecisionRecommendation(Base, TimestampMixin):
    """
    SQLAlchemy model persisting replenishment decision recommendations
    and human-in-the-loop approvals (Member 4).

    Rules:
    - Stores the synthesized outputs of the Inventory, Demand, and Supplier agents.
    - Records deterministic numbers (quantity, costs) and Grok explanation/factors.
    - Tracks approval lifecycle (PENDING -> APPROVED / REJECTED) with audit trail.
    - Holds source agent snapshot for traceability.
    """
    __tablename__ = "decision_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Deterministic calculation metrics
    forecast_horizon_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_available_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    predicted_demand: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lead_time_demand: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stockout_risk_level: Mapped[str] = mapped_column(String(50), default="LOW", nullable=False)

    # Core Decisions
    replenishment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recommended_order_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Selected Supplier
    selected_supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_supplier_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_total_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    # Explainability & AI Synthesis
    risk_level: Mapped[str] = mapped_column(String(50), default="LOW", nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    factors: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    policy_references: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Human-in-the-Loop Governance
    approval_status: Mapped[str] = mapped_column(
        String(50),
        default=ApprovalStatus.PENDING.value,
        server_default=ApprovalStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Full input context snapshot for auditability
    source_agent_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    product = relationship("Product")
    selected_supplier = relationship("Supplier")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return (
            f"<DecisionRecommendation id={self.id} "
            f"product_id={self.product_id} "
            f"replenishment_required={self.replenishment_required} "
            f"quantity={self.recommended_order_quantity} "
            f"status={self.approval_status}>"
        )
