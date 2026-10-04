/**
 * TypeScript type definitions for Member 4 Replenishment Decision Agent
 * and Document Information Retrieval (IR) Evidence provenance.
 *
 * Adheres strictly to the backend schemas in:
 * - app/schemas/decision.py
 * - app/schemas/document_processing.py
 * - app/schemas/supplier_agent.py
 */

export interface DocumentEvidence {
  rank?: number | null;
  chunk_id?: string | null;
  document_id: number;
  document_title: string;
  title?: string | null;
  document_type?: string | null;
  supplier_id?: number | null;
  page_number?: number | null;
  chunk_index?: number | null;
  text: string;
  distance?: number | null;
  source_type: string; // e.g. "document_ir"
  authority: string;   // e.g. "policy_or_sla"
}

export interface ScoreBreakdown {
  cost_score: number;
  delivery_score: number;
  sla_score: number;
  weighted_cost: number;
  weighted_delivery: number;
  weighted_sla: number;
  total_score: number;
  weight_cost: number;
  weight_delivery: number;
  weight_sla: number;
  zero_slack_penalty_applied: boolean;
}

export interface SupplierPolicySignals {
  supplier_id: number;
  supplier_name: string;
  contracted_otif_pct?: number | null;
  historical_otif_pct?: number | null;
  expedited_available: boolean;
  expedited_fee_pct?: number | null;
  standard_lead_time_days?: number | null;
  expedited_lead_time_days?: number | null;
  penalty_clause_present: boolean;
  is_restricted: boolean;
  restriction_reason?: string | null;
  sla_grounded: boolean;
  provenance_evidence: DocumentEvidence[];
}

export interface DetectedProcurementCondition {
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;
  derived_urgency: 'normal' | 'high' | 'emergency' | string;
  effective_urgency: 'normal' | 'high' | 'emergency' | string;
  manual_urgency_override?: string | null;
  manual_override_applied: boolean;
  days_until_stockout?: number | null;
  days_until_unsafe?: number | null;
  required_delivery_window_days?: number | null;
  condition_reason: string;
  weight_cost: number;
  weight_delivery: number;
  weight_sla: number;
  governing_policy_doc?: string | null;
}

export interface SelectedSupplierInfo {
  supplier_id: number;
  supplier_code?: string | null;
  supplier_name: string;
  unit_cost: number;
  moq: number;
  lead_time_days: number;
  estimated_total_cost: number;
  selection_reason: string;
  score?: number | null;
  score_breakdown?: ScoreBreakdown | null;
  delivery_slack_days?: number | null;
  advantages?: string[];
  risks?: string[];
  evidence: DocumentEvidence[];
}

export interface InventorySnapshot {
  product_id: number;
  product_name: string;
  sku?: string | null;
  on_hand: number;
  reserved: number;
  incoming: number;
  available_stock: number;
  effective_inventory?: number | null;
  reorder_point: number;
  status: string;
}

export interface DemandSnapshot {
  product_id: number;
  forecast_horizon_days: number;
  total_forecasted_demand: number;
  lead_time_days: number;
  expected_demand_over_lead_time: number;
  risk_level: string;
  projected_stockout_date?: string | null;
  selected_model?: string | null;
}

export interface SupplierCandidateOption {
  supplier_id: number;
  supplier_code?: string | null;
  supplier_name: string;
  unit_cost: number;
  moq: number;
  lead_time_days: number;
  meets_moq?: boolean | null;
  estimated_cost?: number | null;
  delivery_slack_days?: number | null;
  is_feasible: boolean;
  disqualification_reason?: string | null;
  score?: number | null;
  score_breakdown?: ScoreBreakdown | null;
  signals?: SupplierPolicySignals | null;
  advantages: string[];
  risks: string[];
  evidence: DocumentEvidence[];
}

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export interface DecisionRecommendationResponse {
  id?: number | null;
  product_id: number;
  sku?: string | null;
  product_name: string;
  replenishment_required: boolean;
  recommended_order_quantity: number;
  selected_supplier?: SelectedSupplierInfo | null;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;
  derived_urgency?: string | null;
  effective_urgency?: string | null;
  manual_urgency_override?: string | null;
  manual_override_applied?: boolean;
  required_delivery_window_days?: number | null;
  detected_condition?: DetectedProcurementCondition | null;
  reasoning: string;
  factors: string[];
  warnings: string[];
  policy_references: string[];
  confidence?: number | null;
  approval_status: ApprovalStatus;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  reviewer_notes?: string | null;
  rejection_reason?: string | null;
  created_at?: string | null;
  inventory_context?: InventorySnapshot | null;
  demand_context?: DemandSnapshot | null;
  supplier_options: SupplierCandidateOption[];
}

export interface DecisionRecommendationRequest {
  product_id?: number | null;
  sku?: string | null;
  forecast_horizon_days?: number;
  lead_time_days?: number | null;
  urgency?: string | null;
  urgency_override?: 'auto' | 'normal' | 'high' | 'emergency' | string | null;
}

export interface DecisionApprovalRequest {
  status: ApprovalStatus;
  reviewer_notes?: string | null;
  rejection_reason?: string | null;
}

export interface DecisionListResponse {
  items: DecisionRecommendationResponse[];
  total: number;
}
