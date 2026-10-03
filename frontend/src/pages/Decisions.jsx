import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Sparkles,
  Boxes,
  Truck,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
  RefreshCw,
  Search,
  ArrowRight,
  ChevronRight,
  Info,
  DollarSign,
  FileCheck,
  Layers,
  HelpCircle,
  Eye,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import { useAuth } from '../context/AuthContext';
import { getProducts } from '../services/productApi';
import {
  getRecommendation,
  getDecisionHistory,
  approveDecision,
  rejectDecision,
} from '../services/decisionApi';

export default function Decisions() {
  const { user } = useAuth();

  // Products catalog state
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [forecastHorizon, setForecastHorizon] = useState(14);
  const [urgency, setUrgency] = useState('normal');

  // Recommendation & Agent State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentDecision, setCurrentDecision] = useState(null);
  const [agentError, setAgentError] = useState('');

  // History Log State
  const [historyList, setHistoryList] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  // Approval / Rejection Modal State
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [rejectionModalOpen, setRejectionModalOpen] = useState(false);
  const [actionNotes, setActionNotes] = useState('');
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState('');

  // Active Context Tab
  const [activeTab, setActiveTab] = useState('reasoning'); // 'reasoning' | 'inventory' | 'demand' | 'suppliers'

  // Load products catalog
  useEffect(() => {
    async function loadCatalog() {
      const res = await getProducts({ limit: 200 });
      if (res.success && res.data) {
        setProducts(res.data);
        if (res.data.length > 0 && !selectedProductId) {
          setSelectedProductId(String(res.data[0].id));
        }
      }
    }
    loadCatalog();
  }, []);

  // Load decision history
  const loadHistory = useCallback(async () => {
    setIsLoadingHistory(true);
    const res = await getDecisionHistory({
      limit: 30,
      status: statusFilter || undefined,
    });
    if (res.success && res.data) {
      setHistoryList(res.data.items || []);
    }
    setIsLoadingHistory(false);
  }, [statusFilter]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Selected product object
  const selectedProduct = useMemo(() => {
    return products.find((p) => String(p.id) === String(selectedProductId)) || null;
  }, [products, selectedProductId]);

  // Handle Generate Decision
  const handleGenerateDecision = async (e) => {
    if (e) e.preventDefault();
    if (!selectedProductId) return;

    setIsGenerating(true);
    setAgentError('');

    const res = await getRecommendation({
      productId: Number(selectedProductId),
      forecastHorizonDays: Number(forecastHorizon),
      urgency,
    });

    if (res.success && res.data) {
      setCurrentDecision(res.data);
      loadHistory(); // Refresh audit history
    } else {
      setAgentError(res.error || 'Failed to generate recommendation.');
    }
    setIsGenerating(false);
  };

  // Handle Approve Recommendation
  const handleApprove = async () => {
    if (!currentDecision?.id) return;
    setIsSubmittingAction(true);
    setActionError('');

    const res = await approveDecision(currentDecision.id, {
      reviewerNotes: actionNotes.trim() || 'Approved by procurement manager.',
    });

    if (res.success && res.data) {
      setCurrentDecision(res.data);
      setApprovalModalOpen(false);
      setActionNotes('');
      loadHistory();
    } else {
      setActionError(res.error || 'Approval failed.');
    }
    setIsSubmittingAction(false);
  };

  // Handle Reject Recommendation
  const handleReject = async () => {
    if (!currentDecision?.id) return;
    setIsSubmittingAction(true);
    setActionError('');

    const res = await rejectDecision(currentDecision.id, {
      rejectionReason: actionNotes.trim() || 'Rejected during managerial review.',
    });

    if (res.success && res.data) {
      setCurrentDecision(res.data);
      setRejectionModalOpen(false);
      setActionNotes('');
      loadHistory();
    } else {
      setActionError(res.error || 'Rejection failed.');
    }
    setIsSubmittingAction(false);
  };

  // Status badges helper
  const renderStatusBadge = (status) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Approved
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle className="w-3 h-3" /> Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3 h-3" /> Pending Review
          </span>
        );
    }
  };

  const renderRiskBadge = (risk) => {
    switch (risk?.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/30 uppercase tracking-wide">
            Critical Risk
          </span>
        );
      case 'HIGH':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase tracking-wide">
            High Risk
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-300 border border-blue-500/30 uppercase tracking-wide">
            Medium Risk
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase tracking-wide">
            Low Risk
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Header section */}
        <section className="space-y-2">
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                Replenishment Decision Agent
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
                  Member 4 • Grok AI
                </span>
              </h1>
              <p className="text-xs sm:text-sm text-neutral-400">
                Autonomous multi-agent synthesis: evaluates inventory status, statistical demand risk, and supplier SLA contracts to deliver human-supervised replenishment decisions.
              </p>
            </div>
          </div>
        </section>

        {/* Interactive Analyzer Panel */}
        <section className="p-6 rounded-2xl bg-neutral-900/40 border border-white/[0.06] backdrop-blur-xl space-y-5">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 flex items-center gap-2">
            <Layers className="w-4 h-4 text-violet-400" /> Decision Input & Multi-Agent Context
          </h2>

          <form onSubmit={handleGenerateDecision} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Product Select */}
            <div className="space-y-1.5 sm:col-span-2">
              <label className="text-xs font-medium text-neutral-300">Target Catalog Product</label>
              <select
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
                className="w-full bg-neutral-950/70 border border-white/[0.08] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-violet-500/50"
              >
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku}) • ROP: {p.reorder_point} units
                  </option>
                ))}
              </select>
            </div>

            {/* Forecast Horizon */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">Forecast Horizon</label>
              <select
                value={forecastHorizon}
                onChange={(e) => setForecastHorizon(Number(e.target.value))}
                className="w-full bg-neutral-950/70 border border-white/[0.08] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-violet-500/50"
              >
                <option value={7}>7 Days (Short Term)</option>
                <option value={14}>14 Days (Standard)</option>
                <option value={30}>30 Days (Monthly)</option>
              </select>
            </div>

            {/* Procurement Urgency */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-300">Procurement Urgency</label>
              <select
                value={urgency}
                onChange={(e) => setUrgency(e.target.value)}
                className="w-full bg-neutral-950/70 border border-white/[0.08] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-violet-500/50"
              >
                <option value="normal">Normal (Cost Optimized)</option>
                <option value="high">High (Balanced)</option>
                <option value="emergency">Emergency (Lead Time Critical)</option>
              </select>
            </div>

            {/* Submit Action */}
            <div className="sm:col-span-2 lg:col-span-4 flex items-center justify-between pt-2">
              <div className="text-xs text-neutral-400">
                {selectedProduct && (
                  <span>
                    Selected: <strong className="text-white">{selectedProduct.name}</strong> • SKU:{' '}
                    <code className="text-violet-300">{selectedProduct.sku}</code>
                  </span>
                )}
              </div>

              <button
                type="submit"
                disabled={isGenerating || !selectedProductId}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white text-xs font-semibold shadow-lg shadow-violet-500/20 disabled:opacity-50 transition"
              >
                {isGenerating ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Synthesizing Agents...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Run Decision Agent</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {agentError && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span>{agentError}</span>
            </div>
          )}
        </section>

        {/* Active Recommendation Output Card */}
        {currentDecision && (
          <section className="rounded-2xl bg-neutral-900/60 border border-violet-500/30 overflow-hidden shadow-2xl shadow-violet-500/5 space-y-6">
            {/* Top Banner */}
            <div className="p-6 bg-gradient-to-r from-violet-950/40 via-neutral-900/40 to-neutral-900/20 border-b border-white/[0.06] flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <span className="text-xs text-neutral-400 uppercase tracking-wider font-semibold">
                    Decision Analysis Result
                  </span>
                  {renderStatusBadge(currentDecision.approval_status)}
                  {renderRiskBadge(currentDecision.risk_level)}
                </div>
                <h3 className="text-lg font-bold text-white mt-1">
                  {currentDecision.product_name}{' '}
                  <span className="text-xs font-mono font-normal text-neutral-400">
                    ({currentDecision.sku})
                  </span>
                </h3>
              </div>

              {/* Action Buttons for Human Approval */}
              {currentDecision.approval_status === 'PENDING' && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setActionNotes('');
                      setRejectionModalOpen(true);
                    }}
                    className="px-3.5 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-300 text-xs font-medium transition"
                  >
                    Reject Recommendation
                  </button>
                  <button
                    onClick={() => {
                      setActionNotes('');
                      setApprovalModalOpen(true);
                    }}
                    className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 transition flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Approve Requisition</span>
                  </button>
                </div>
              )}
            </div>

            {/* Core Outputs Triad Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 px-6">
              {/* Output 1: Replenishment Required */}
              <div className="p-4 rounded-xl bg-neutral-950/60 border border-white/[0.06] space-y-1.5">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-medium flex items-center gap-1.5">
                  <Boxes className="w-3.5 h-3.5 text-teal-400" /> Replenishment Required
                </span>
                <div className="flex items-baseline gap-2">
                  <span
                    className={`text-2xl font-black tracking-tight ${
                      currentDecision.replenishment_required ? 'text-teal-400' : 'text-neutral-300'
                    }`}
                  >
                    {currentDecision.replenishment_required ? 'YES' : 'NO'}
                  </span>
                  <span className="text-xs text-neutral-500">
                    {currentDecision.replenishment_required ? 'Restock order triggered' : 'Inventory adequate'}
                  </span>
                </div>
              </div>

              {/* Output 2: Recommended Order Quantity */}
              <div className="p-4 rounded-xl bg-neutral-950/60 border border-white/[0.06] space-y-1.5">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-medium flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-violet-400" /> Recommended Order Quantity
                </span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black text-white tracking-tight">
                    {currentDecision.recommended_order_quantity.toLocaleString()}
                  </span>
                  <span className="text-xs text-neutral-400">units (clamped non-negative)</span>
                </div>
              </div>

              {/* Output 3: Recommended Supplier */}
              <div className="p-4 rounded-xl bg-neutral-950/60 border border-white/[0.06] space-y-1.5">
                <span className="text-[11px] text-neutral-400 uppercase tracking-wider font-medium flex items-center gap-1.5">
                  <Truck className="w-3.5 h-3.5 text-blue-400" /> Designated Supplier
                </span>
                {currentDecision.selected_supplier ? (
                  <div>
                    <div className="text-sm font-semibold text-white truncate">
                      {currentDecision.selected_supplier.supplier_name}
                    </div>
                    <div className="text-[11px] text-neutral-400 flex items-center gap-2 mt-0.5">
                      <span>LKR {currentDecision.selected_supplier.unit_cost.toLocaleString()} / unit</span>
                      <span>•</span>
                      <span>{currentDecision.selected_supplier.lead_time_days}d lead time</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-neutral-500 italic">None (No order required or no vendor)</div>
                )}
              </div>
            </div>

            {/* Warnings alert if any */}
            {currentDecision.warnings && currentDecision.warnings.length > 0 && (
              <div className="mx-6 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-1">
                <div className="flex items-center gap-1.5 text-amber-400 text-xs font-semibold">
                  <AlertTriangle className="w-3.5 h-3.5" /> Operational Notices & Missing Data Safeguards:
                </div>
                <ul className="text-xs text-amber-300/90 list-disc list-inside space-y-0.5 pl-1">
                  {currentDecision.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Context Navigation Tabs */}
            <div className="px-6 border-b border-white/[0.06] flex items-center gap-3 text-xs">
              <button
                onClick={() => setActiveTab('reasoning')}
                className={`pb-2.5 font-medium border-b-2 transition ${
                  activeTab === 'reasoning'
                    ? 'border-violet-400 text-violet-300'
                    : 'border-transparent text-neutral-400 hover:text-white'
                }`}
              >
                Grok AI Explainability & Synthesis
              </button>
              <button
                onClick={() => setActiveTab('inventory')}
                className={`pb-2.5 font-medium border-b-2 transition ${
                  activeTab === 'inventory'
                    ? 'border-teal-400 text-teal-300'
                    : 'border-transparent text-neutral-400 hover:text-white'
                }`}
              >
                Inventory Agent Data
              </button>
              <button
                onClick={() => setActiveTab('demand')}
                className={`pb-2.5 font-medium border-b-2 transition ${
                  activeTab === 'demand'
                    ? 'border-blue-400 text-blue-300'
                    : 'border-transparent text-neutral-400 hover:text-white'
                }`}
              >
                Demand & Risk Data
              </button>
              <button
                onClick={() => setActiveTab('suppliers')}
                className={`pb-2.5 font-medium border-b-2 transition ${
                  activeTab === 'suppliers'
                    ? 'border-emerald-400 text-emerald-300'
                    : 'border-transparent text-neutral-400 hover:text-white'
                }`}
              >
                Supplier Options Evaluated ({currentDecision.supplier_options?.length || 0})
              </button>
            </div>

            {/* Tab Contents */}
            <div className="px-6 pb-6">
              {/* Tab 1: Reasoning */}
              {activeTab === 'reasoning' && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-neutral-950/70 border border-violet-500/20 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-violet-300 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" /> Grok LLM Explainable Rationale
                      </span>
                      {currentDecision.confidence !== null && (
                        <span className="text-neutral-400 font-mono text-[11px]">
                          Confidence: {(currentDecision.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-neutral-200 leading-relaxed whitespace-pre-line">
                      {currentDecision.reasoning}
                    </p>
                  </div>

                  {/* Key Factors */}
                  {currentDecision.factors && currentDecision.factors.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                        Key Factors Considered
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                        {currentDecision.factors.map((factor, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] text-neutral-300 flex items-start gap-2"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-teal-400 mt-0.5 flex-shrink-0" />
                            <span>{factor}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Policy References */}
                  {currentDecision.policy_references && currentDecision.policy_references.length > 0 && (
                    <div className="space-y-1.5 pt-2">
                      <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                        Corporate Policies Referenced
                      </h4>
                      <div className="text-xs text-neutral-400 space-y-1">
                        {currentDecision.policy_references.map((p, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <ShieldCheck className="w-3.5 h-3.5 text-violet-400" />
                            <span>{p}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Inventory Agent Snapshot */}
              {activeTab === 'inventory' && (
                <div className="p-4 rounded-xl bg-neutral-950/60 border border-white/[0.06] space-y-4 text-xs">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <span className="font-semibold text-white">Inventory Agent (Member 1) Snapshot</span>
                    <span className="font-mono text-teal-400 uppercase">
                      Status: {currentDecision.inventory_context?.status || 'HEALTHY'}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">On-Hand</div>
                      <div className="text-base font-bold text-white mt-1">
                        {currentDecision.inventory_context?.on_hand ?? '-'}
                      </div>
                    </div>
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Reserved</div>
                      <div className="text-base font-bold text-white mt-1">
                        {currentDecision.inventory_context?.reserved ?? '-'}
                      </div>
                    </div>
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Available Stock</div>
                      <div className="text-base font-bold text-teal-400 mt-1">
                        {currentDecision.inventory_context?.available_stock ?? '-'}
                      </div>
                    </div>
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Reorder Point (ROP)</div>
                      <div className="text-base font-bold text-violet-400 mt-1">
                        {currentDecision.inventory_context?.reorder_point ?? '-'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 3: Demand Agent Snapshot */}
              {activeTab === 'demand' && (
                <div className="p-4 rounded-xl bg-neutral-950/60 border border-white/[0.06] space-y-4 text-xs">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <span className="font-semibold text-white">Demand & Risk Agent (Member 2) Snapshot</span>
                    <span className="font-mono text-blue-400 uppercase">
                      Model: {currentDecision.demand_context?.selected_model || 'SMA Forecast'}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Forecast Horizon</div>
                      <div className="text-base font-bold text-white mt-1">
                        {currentDecision.demand_context?.forecast_horizon_days ?? 14} days
                      </div>
                    </div>
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Total Forecast Demand</div>
                      <div className="text-base font-bold text-blue-400 mt-1">
                        {currentDecision.demand_context?.total_forecasted_demand ?? 0} units
                      </div>
                    </div>
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Lead-Time Demand</div>
                      <div className="text-base font-bold text-white mt-1">
                        {currentDecision.demand_context?.expected_demand_over_lead_time ?? 0} units
                      </div>
                    </div>
                    <div className="p-3 bg-white/[0.02] rounded-lg">
                      <div className="text-neutral-400 text-[10px]">Projected Stockout</div>
                      <div className="text-base font-bold text-amber-400 mt-1">
                        {currentDecision.demand_context?.projected_stockout_date || 'None in period'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 4: Supplier Intelligence Snapshot */}
              {activeTab === 'suppliers' && (
                <div className="space-y-3">
                  <div className="text-xs text-neutral-400">
                    Evaluated supplier commercial candidates provided by Supplier Intelligence Agent (Member 3):
                  </div>
                  <div className="space-y-2">
                    {currentDecision.supplier_options?.map((sup) => {
                      const isSelected =
                        currentDecision.selected_supplier?.supplier_id === sup.supplier_id;
                      return (
                        <div
                          key={sup.supplier_id}
                          className={`p-3.5 rounded-xl border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                            isSelected
                              ? 'bg-violet-950/30 border-violet-500/40 shadow-sm'
                              : 'bg-neutral-950/50 border-white/[0.04]'
                          }`}
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-white text-sm">
                                {sup.supplier_name}
                              </span>
                              {isSelected && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-violet-500/20 text-violet-300">
                                  Selected Candidate
                                </span>
                              )}
                            </div>
                            <div className="text-neutral-400 text-[11px] mt-0.5 flex gap-3">
                              <span>Unit Cost: LKR {sup.unit_cost.toLocaleString()}</span>
                              <span>MOQ: {sup.moq} units</span>
                              <span>Lead Time: {sup.lead_time_days} days</span>
                            </div>
                          </div>

                          <div className="text-neutral-300 text-[11px]">
                            {sup.advantages && sup.advantages.length > 0 && (
                              <span className="text-teal-400 block">{sup.advantages[0]}</span>
                            )}
                            {sup.risks && sup.risks.length > 0 && (
                              <span className="text-amber-400 block">{sup.risks[0]}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Historical Decisions Table */}
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400">
                Decision & Approval History
              </h2>
              <p className="text-xs text-neutral-500">
                Audit trail of generated replenishment recommendations and managerial decisions.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-neutral-900 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-neutral-300 focus:outline-none"
              >
                <option value="">All Statuses</option>
                <option value="PENDING">Pending Review</option>
                <option value="APPROVED">Approved</option>
                <option value="REJECTED">Rejected</option>
              </select>

              <button
                onClick={loadHistory}
                className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-neutral-400 hover:text-white transition"
                title="Refresh History"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-white/[0.06] bg-neutral-900/40 backdrop-blur-xl overflow-hidden">
            {isLoadingHistory ? (
              <div className="p-8 text-center text-xs text-neutral-500 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-violet-400" />
                <span>Loading audit log...</span>
              </div>
            ) : historyList.length === 0 ? (
              <div className="p-8 text-center text-xs text-neutral-500">
                No decision history records found.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/[0.06] bg-white/[0.02] text-neutral-400 uppercase tracking-wider font-semibold text-[10px]">
                    <tr>
                      <th className="py-3 px-4">ID</th>
                      <th className="py-3 px-4">Product</th>
                      <th className="py-3 px-4">Replenish?</th>
                      <th className="py-3 px-4">Quantity</th>
                      <th className="py-3 px-4">Designated Supplier</th>
                      <th className="py-3 px-4">Risk</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {historyList.map((item) => (
                      <tr key={item.id} className="hover:bg-white/[0.02] transition">
                        <td className="py-3 px-4 font-mono text-neutral-400">#{item.id}</td>
                        <td className="py-3 px-4">
                          <div className="font-medium text-white">{item.product_name}</div>
                          <div className="text-[10px] text-neutral-500">{item.sku}</div>
                        </td>
                        <td className="py-3 px-4 font-semibold">
                          {item.replenishment_required ? (
                            <span className="text-teal-400">YES</span>
                          ) : (
                            <span className="text-neutral-500">NO</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-white">
                          {item.recommended_order_quantity.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-neutral-300">
                          {item.selected_supplier?.supplier_name || '—'}
                        </td>
                        <td className="py-3 px-4">{renderRiskBadge(item.risk_level)}</td>
                        <td className="py-3 px-4">{renderStatusBadge(item.approval_status)}</td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setCurrentDecision(item)}
                            className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-neutral-300 hover:text-white transition inline-flex items-center gap-1"
                          >
                            <Eye className="w-3 h-3" />
                            <span>View</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* Approval Confirmation Modal */}
      {approvalModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="max-w-md w-full rounded-2xl bg-neutral-900 border border-white/[0.08] p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" /> Confirm Human Requisition Approval
            </h3>
            <p className="text-xs text-neutral-300 leading-relaxed">
              You are approving the replenishment recommendation for{' '}
              <strong className="text-white">{currentDecision?.product_name}</strong> for{' '}
              <strong className="text-emerald-400">
                {currentDecision?.recommended_order_quantity} units
              </strong>{' '}
              from{' '}
              <strong className="text-white">
                {currentDecision?.selected_supplier?.supplier_name}
              </strong>
              .
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-400">
                Manager Review Notes / PO Reference:
              </label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="e.g. Approved for PO generation under standard procurement limits."
                className="w-full bg-neutral-950/80 border border-white/[0.08] rounded-xl p-3 text-xs text-white focus:outline-none focus:border-emerald-500/50"
              />
            </div>

            {actionError && <div className="text-xs text-rose-400">{actionError}</div>}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setApprovalModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmittingAction}
                onClick={handleApprove}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 transition disabled:opacity-50"
              >
                {isSubmittingAction ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {rejectionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="max-w-md w-full rounded-2xl bg-neutral-900 border border-white/[0.08] p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <XCircle className="w-5 h-5 text-rose-400" /> Reject Replenishment Recommendation
            </h3>
            <p className="text-xs text-neutral-300 leading-relaxed">
              Please enter the managerial justification for rejecting this recommendation.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-neutral-400">Rejection Justification:</label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="e.g. Budgetary freeze in current cycle; re-evaluate in 30 days."
                className="w-full bg-neutral-950/80 border border-white/[0.08] rounded-xl p-3 text-xs text-white focus:outline-none focus:border-rose-500/50"
              />
            </div>

            {actionError && <div className="text-xs text-rose-400">{actionError}</div>}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setRejectionModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmittingAction}
                onClick={handleReject}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/20 transition disabled:opacity-50"
              >
                {isSubmittingAction ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
