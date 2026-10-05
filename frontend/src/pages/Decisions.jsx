import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  Info,
  FileText,
  ChevronDown,
  ChevronUp,
  Scale,
  Building2,
  Check,
  Eye,
  UserCheck,
  ArrowRight,
  ExternalLink,
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
  const { user, isAdmin } = useAuth();

  // Products catalog state
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [forecastHorizon, setForecastHorizon] = useState(14);
  const [urgencyOverride, setUrgencyOverride] = useState('auto');
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);

  // Recommendation & Agent State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentDecision, setCurrentDecision] = useState(null);
  const [agentError, setAgentError] = useState('');

  // UI View toggles
  const [showScoringDetails, setShowScoringDetails] = useState(false);
  const [openAccordions, setOpenAccordions] = useState({
    sla: false,
    performance: false,
    policy: false,
    warnings: false,
  });

  // Section Refs for quick jumping
  const supplierSectionRef = useRef(null);
  const evidenceSectionRef = useRef(null);

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

  const toggleAccordion = (key) => {
    setOpenAccordions((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const scrollToSuppliers = () => {
    supplierSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToEvidence = () => {
    setOpenAccordions((prev) => ({ ...prev, sla: true, policy: true }));
    setTimeout(() => {
      evidenceSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  };

  // Safe document type label formatter
  const formatDocumentType = (type) => {
    if (!type) return 'Document IR';
    switch (type.toLowerCase()) {
      case 'supplier_sla':
        return 'Supplier SLA';
      case 'procurement_policy':
        return 'Procurement Policy';
      case 'supplier_contract':
        return 'Supplier Contract';
      case 'performance_review':
        return 'Performance Review';
      default:
        return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    }
  };

  const formatPageLabel = (pageNumber) => {
    if (pageNumber === null || pageNumber === undefined) return null;
    return `Page ${pageNumber}`;
  };

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
      urgencyOverride: urgencyOverride !== 'auto' ? urgencyOverride : undefined,
    });

    if (res.success && res.data) {
      setCurrentDecision(res.data);
      loadHistory();
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
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 font-mono">
            <CheckCircle2 className="w-3 h-3" /> Approved
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
            <XCircle className="w-3 h-3" /> Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#CEF431]/20 text-[#CEF431] border border-[#CEF431]/30 font-mono">
            <Clock className="w-3 h-3" /> Pending Review
          </span>
        );
    }
  };

  const renderUrgencyBadge = (urgency) => {
    const u = urgency?.toUpperCase();
    if (u === 'EMERGENCY') {
      return (
        <span className="text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 uppercase tracking-wide">
          EMERGENCY
        </span>
      );
    }
    if (u === 'EXPEDITED' || u === 'HIGH') {
      return (
        <span className="text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase tracking-wide">
          EXPEDITED
        </span>
      );
    }
    return (
      <span className="text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 uppercase tracking-wide">
        NORMAL
      </span>
    );
  };

  const renderRiskBadge = (risk) => {
    switch (risk?.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/30 uppercase tracking-wide">
            Critical Risk
          </span>
        );
      case 'HIGH':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase tracking-wide">
            High Risk
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 uppercase tracking-wide">
            Medium Risk
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 uppercase tracking-wide">
            Low Risk
          </span>
        );
    }
  };

  const renderSlackBadge = (slack) => {
    if (slack === null || slack === undefined) return <span className="text-[#EAF4F4]/40">—</span>;
    if (slack > 0) {
      return (
        <span className="inline-flex items-center text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
          +{slack}d
        </span>
      );
    } else if (slack === 0) {
      return (
        <span className="inline-flex items-center text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
          0d (Critical)
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30">
          {slack}d
        </span>
      );
    }
  };

  // 3-5 concise "Why this decision?" bullets
  const decisionReasons = useMemo(() => {
    if (!currentDecision) return [];

    const bullets = [];

    // Factor 1: Inventory position & ROP status
    const inv = currentDecision.inventory_context;
    const cond = currentDecision.detected_condition;
    if (cond?.days_until_buffer_breach === 0 || (inv && inv.available_stock <= inv.reorder_point)) {
      bullets.push('The ROP safety buffer is already breached under current available inventory.');
    } else if (cond?.days_until_buffer_breach != null) {
      bullets.push(`ROP buffer is projected to breach in approximately ${cond.days_until_buffer_breach} days.`);
    }

    // Factor 2: Available stock exhaustion timing
    if (cond?.days_until_stockout != null) {
      bullets.push(`Available inventory may be exhausted in approximately ${cond.days_until_stockout} days.`);
    } else if (inv && inv.available_stock > 0) {
      bullets.push(`Current warehouse inventory has ${inv.available_stock} units available to fulfill.`);
    }

    // Factor 3: Supplier delivery feasibility
    const sup = currentDecision.selected_supplier;
    const reqDays = cond?.required_delivery_window_days ?? currentDecision.required_delivery_window_days;
    if (sup && reqDays != null) {
      bullets.push(
        `${sup.supplier_name} satisfies the required delivery window of ≤ ${reqDays} days (lead time: ${sup.lead_time_days} days).`
      );
    } else if (sup) {
      bullets.push(`${sup.supplier_name} provides the most competitive combination of lead time and commercial pricing.`);
    }

    // Factor 4: Grounded SLA or policy justification
    if (sup?.evidence && sup.evidence.length > 0) {
      bullets.push(`${sup.supplier_name} is backed by verified emergency/contract SLA documentation.`);
    } else if (currentDecision.policy_references && currentDecision.policy_references.length > 0) {
      bullets.push('Recommendation complies with active corporate procurement replenishment policies.');
    }

    // If factors from backend exists and bullets < 3, backfill with concise factors
    if (currentDecision.factors && currentDecision.factors.length > 0 && bullets.length < 3) {
      for (const f of currentDecision.factors) {
        if (!bullets.includes(f) && bullets.length < 5) {
          bullets.push(f);
        }
      }
    }

    return bullets.slice(0, 5);
  }, [currentDecision]);

  // Derived effective urgency
  const effectiveUrgency =
    currentDecision?.detected_condition?.effective_urgency ||
    currentDecision?.urgency_level ||
    (currentDecision?.replenishment_required ? 'EMERGENCY' : 'NORMAL');

  // Delivery window
  const requiredDelivery =
    currentDecision?.detected_condition?.required_delivery_window_days ??
    currentDecision?.required_delivery_window_days ??
    currentDecision?.selected_supplier?.required_delivery_window_days;

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col font-sans selection:bg-[#03D26F]/30 selection:text-white">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* STANDARDIZED PAGE HEADER & INPUT CONTROLS */}
        <section className="bg-[#01353e]/70 border border-white/[0.08] rounded-3xl p-6 sm:p-7 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.06] pb-4">
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                DECISION INTELLIGENCE
              </h1>
              <p className="text-xs sm:text-sm text-[#EAF4F4]/70 mt-1">
                Generate an inventory replenishment and supplier recommendation.
              </p>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-auto bg-[#01272e]/80 border border-white/[0.08] px-3 py-1.5 rounded-2xl text-xs font-mono">
              <span className="text-[#EAF4F4]/60">Role:</span>
              <span className="text-[#03D26F] font-bold">{user?.role}</span>
              <span className="text-white/[0.2]">•</span>
              <span className="text-[11px] text-[#CEF431]">
                {isAdmin ? 'Approval Authority' : 'View Only'}
              </span>
            </div>
          </div>

          {/* Input Controls */}
          <form onSubmit={handleGenerateDecision} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3.5 items-end">
              {/* Product Selector */}
              <div className="sm:col-span-6 space-y-1.5">
                <label className="text-xs font-semibold text-[#EAF4F4]/90 block">
                  Select Product
                </label>
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value)}
                  className="w-full bg-[#01272e] border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/30"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id} className="bg-[#01272e] text-white">
                      {p.name} ({p.sku}) • ROP: {p.reorder_point} units
                    </option>
                  ))}
                </select>
              </div>

              {/* Forecast Horizon Selector */}
              <div className="sm:col-span-3 space-y-1.5">
                <label className="text-xs font-semibold text-[#EAF4F4]/90 block">
                  Forecast Horizon
                </label>
                <select
                  value={forecastHorizon}
                  onChange={(e) => setForecastHorizon(Number(e.target.value))}
                  className="w-full bg-[#01272e] border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/30"
                >
                  <option value={7} className="bg-[#01272e] text-white">7 Days (Short Term)</option>
                  <option value={14} className="bg-[#01272e] text-white">14 Days (Standard)</option>
                  <option value={30} className="bg-[#01272e] text-white">30 Days (Monthly)</option>
                </select>
              </div>

              {/* Analyze Button */}
              <div className="sm:col-span-3">
                <button
                  type="submit"
                  disabled={isGenerating || !selectedProductId}
                  className="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-[#03D26F] hover:bg-[#02be63] text-[#161514] text-xs font-bold shadow-lg shadow-[#03D26F]/25 disabled:opacity-50 transition cursor-pointer"
                >
                  {isGenerating ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#161514]" />
                      <span>Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5 text-[#161514]" />
                      <span>Analyze Decision</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Advanced Options (Optional Urgency Override Only) */}
            <div className="pt-0.5">
              <button
                type="button"
                onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                className="text-xs font-medium text-[#03D26F] hover:text-[#02be63] flex items-center gap-1.5 transition cursor-pointer"
              >
                {showAdvancedOptions ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
                <span>Advanced Options {showAdvancedOptions ? '▲' : '▼'} (Urgency Override)</span>
              </button>

              {showAdvancedOptions && (
                <div className="mt-3 p-4 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-2 max-w-xl animate-in fade-in duration-150">
                  <label className="text-xs font-semibold text-[#EAF4F4]/80 flex items-center justify-between">
                    <span>Urgency Override</span>
                    <span className="text-[10px] font-mono text-[#CEF431]">Audited in decision ledger</span>
                  </label>
                  <select
                    value={urgencyOverride}
                    onChange={(e) => setUrgencyOverride(e.target.value)}
                    className="w-full bg-[#01353e] border border-white/[0.1] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#03D26F]"
                  >
                    <option value="auto">Auto-detect (Recommended — derived from stock, forecast & lead times)</option>
                    <option value="normal">Normal (Cost Priority)</option>
                    <option value="high">High (Balanced Delivery & Cost)</option>
                    <option value="emergency">Emergency (Fastest Feasible Delivery)</option>
                  </select>
                </div>
              )}
            </div>
          </form>

          {agentError && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{agentError}</span>
            </div>
          )}
        </section>

        {/* AFTER ANALYSIS RESULTS */}
        {currentDecision && (
          <div className="space-y-6">
            {/* A. DECISION SUMMARY — FIRST */}
            <section className="rounded-3xl bg-gradient-to-br from-[#01353e] via-[#01353e]/95 to-[#014651]/80 border border-[#03D26F]/40 p-6 sm:p-8 shadow-xl space-y-6">
              {/* Recommendation Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
                <div>
                  <div className="flex flex-wrap items-center gap-2.5 mb-1.5">
                    <span className="text-xs uppercase tracking-wider text-[#EAF4F4]/60 font-semibold font-mono">
                      Recommendation
                    </span>
                    {renderUrgencyBadge(effectiveUrgency)}
                    {renderStatusBadge(currentDecision.approval_status)}
                  </div>
                  <h2 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                    {currentDecision.product_name}
                  </h2>
                  <div className="text-xs text-[#EAF4F4]/60 font-mono mt-0.5">
                    SKU: {currentDecision.sku}
                  </div>
                </div>

                {/* HITL Review Actions if Pending */}
                {currentDecision.approval_status === 'PENDING' && (
                  isAdmin ? (
                    <div className="flex items-center gap-2.5 self-start sm:self-auto shrink-0">
                      <button
                        type="button"
                        onClick={() => {
                          setActionNotes('');
                          setRejectionModalOpen(true);
                        }}
                        className="px-4 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 text-xs font-semibold transition cursor-pointer"
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setActionNotes('');
                          setApprovalModalOpen(true);
                        }}
                        className="px-5 py-2 rounded-xl bg-[#03D26F] hover:bg-[#02be63] text-[#161514] text-xs font-bold shadow-lg shadow-[#03D26F]/25 transition flex items-center gap-1.5 cursor-pointer"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-[#161514]" />
                        <span>Approve Requisition</span>
                      </button>
                    </div>
                  ) : (
                    <div className="text-xs text-[#EAF4F4]/70 flex items-center gap-2 bg-[#01272e]/80 px-3.5 py-2 rounded-xl border border-white/[0.08]">
                      <Clock className="w-3.5 h-3.5 text-[#CEF431]" />
                      <span>Pending Administrator Review</span>
                    </div>
                  )
                )}
              </div>

              {/* Large Clean Stats Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* 1. Recommended Order */}
                <div className="p-4 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#EAF4F4]/60 block">
                    Recommended Order
                  </span>
                  <div className="text-2xl sm:text-3xl font-black text-[#03D26F] font-mono">
                    {currentDecision.recommended_order_quantity.toLocaleString()} units
                  </div>
                  <span className="text-[11px] text-[#EAF4F4]/50 block">
                    {currentDecision.replenishment_required ? 'Clamped replenishment order' : 'Stock sufficient'}
                  </span>
                </div>

                {/* 2. Supplier */}
                <div className="p-4 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#EAF4F4]/60 block">
                    Supplier
                  </span>
                  <div className="text-lg sm:text-xl font-bold text-white truncate">
                    {currentDecision.selected_supplier?.supplier_name || 'No supplier needed'}
                  </div>
                  <span className="text-[11px] text-cyan-300 font-mono block">
                    {currentDecision.selected_supplier?.supplier_code || '—'}
                  </span>
                </div>

                {/* 3. Required Delivery */}
                <div className="p-4 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#EAF4F4]/60 block">
                    Required Delivery
                  </span>
                  <div className="text-2xl sm:text-3xl font-black text-cyan-200 font-mono">
                    {requiredDelivery != null ? `≤ ${requiredDelivery} days` : 'Unconstrained'}
                  </div>
                  <span className="text-[11px] text-[#EAF4F4]/50 block">
                    Lead time: {currentDecision.selected_supplier?.lead_time_days ?? '—'}d
                  </span>
                </div>

                {/* 4. Estimated Spend */}
                <div className="p-4 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#EAF4F4]/60 block">
                    Estimated Spend
                  </span>
                  <div className="text-2xl sm:text-3xl font-black text-[#CEF431] font-mono">
                    {currentDecision.selected_supplier?.estimated_total_cost
                      ? `LKR ${currentDecision.selected_supplier.estimated_total_cost.toLocaleString()}`
                      : 'LKR 0'}
                  </div>
                  <span className="text-[11px] text-[#EAF4F4]/50 block">
                    {currentDecision.selected_supplier?.unit_cost
                      ? `@ LKR ${currentDecision.selected_supplier.unit_cost.toLocaleString()} / unit`
                      : 'No spend committed'}
                  </span>
                </div>
              </div>

              {/* Quick Jump Action Links */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <button
                  type="button"
                  onClick={scrollToSuppliers}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] text-xs font-semibold text-white border border-white/[0.1] transition cursor-pointer"
                >
                  <Truck className="w-3.5 h-3.5 text-cyan-300" />
                  <span>View Supplier Comparison</span>
                </button>
                <button
                  type="button"
                  onClick={scrollToEvidence}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] text-xs font-semibold text-white border border-white/[0.1] transition cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5 text-[#03D26F]" />
                  <span>View Evidence & Policy</span>
                </button>
              </div>
            </section>

            {/* B. WHY THIS DECISION? */}
            <section className="rounded-3xl bg-[#01353e]/60 border border-white/[0.08] p-6 sm:p-7 shadow-sm space-y-4">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-[#03D26F]/20 text-[#03D26F] flex items-center justify-center">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Why this decision?
                </h3>
              </div>

              {/* 3–5 Clean Reasons */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {decisionReasons.map((reason, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-2xl bg-[#01272e]/80 border border-white/[0.06] flex items-start gap-2.5 text-xs text-[#EAF4F4]/90 leading-relaxed"
                  >
                    <span className="text-[#03D26F] font-bold text-base leading-none">•</span>
                    <span>{reason}</span>
                  </div>
                ))}
              </div>
            </section>

            {/* C. KEY STATUS CARDS */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#EAF4F4]/70 px-1 font-mono">
                Key Status Telemetry
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* 1. Inventory Card */}
                <div className="p-4 rounded-2xl bg-[#01353e]/60 border border-white/[0.08] space-y-2">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <span className="text-xs font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
                      <Boxes className="w-3.5 h-3.5 text-[#03D26F]" /> Inventory
                    </span>
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                        currentDecision.detected_condition?.days_until_buffer_breach === 0 ||
                        (currentDecision.inventory_context?.available_stock <= currentDecision.inventory_context?.reorder_point)
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      }`}
                    >
                      {currentDecision.detected_condition?.days_until_buffer_breach === 0 ||
                      (currentDecision.inventory_context?.available_stock <= currentDecision.inventory_context?.reorder_point)
                        ? 'BREACHED NOW'
                        : 'BUFFER SAFE'}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Available:</span>
                      <strong className="text-white">
                        {currentDecision.inventory_context?.available_stock ?? '—'}
                      </strong>
                    </div>
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Incoming:</span>
                      <strong className="text-cyan-300">
                        {currentDecision.inventory_context?.incoming ?? 0}
                      </strong>
                    </div>
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>ROP:</span>
                      <strong className="text-[#CEF431]">
                        {currentDecision.inventory_context?.reorder_point ?? '—'}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* 2. Demand Card */}
                <div className="p-4 rounded-2xl bg-[#01353e]/60 border border-white/[0.08] space-y-2">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <span className="text-xs font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5 text-cyan-300" /> Demand
                    </span>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                      {currentDecision.demand_context?.selected_model || 'SMA'}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Forecast:</span>
                      <strong className="text-white">
                        {currentDecision.demand_context?.total_forecasted_demand ?? '—'} units
                      </strong>
                    </div>
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Horizon:</span>
                      <strong className="text-white">
                        {currentDecision.demand_context?.forecast_horizon_days ?? forecastHorizon} days
                      </strong>
                    </div>
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Lead Demand:</span>
                      <strong className="text-cyan-300">
                        {currentDecision.demand_context?.expected_demand_over_lead_time ?? '—'} units
                      </strong>
                    </div>
                  </div>
                </div>

                {/* 3. Risk Card */}
                <div className="p-4 rounded-2xl bg-[#01353e]/60 border border-white/[0.08] space-y-2">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <span className="text-xs font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-300" /> Risk
                    </span>
                    {renderRiskBadge(currentDecision.risk_level || currentDecision.detected_condition?.risk_level)}
                  </div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Available exhaustion:</span>
                      <strong className="text-rose-300">
                        {currentDecision.detected_condition?.days_until_stockout != null
                          ? `~${currentDecision.detected_condition.days_until_stockout} days`
                          : 'No stockout'}
                      </strong>
                    </div>
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Buffer breach:</span>
                      <strong className="text-amber-300">
                        {currentDecision.detected_condition?.days_until_buffer_breach === 0
                          ? 'BREACHED NOW'
                          : currentDecision.detected_condition?.days_until_buffer_breach != null
                          ? `~${currentDecision.detected_condition.days_until_buffer_breach} days`
                          : 'Safe'}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* 4. Procurement Card */}
                <div className="p-4 rounded-2xl bg-[#01353e]/60 border border-white/[0.08] space-y-2">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <span className="text-xs font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
                      <Truck className="w-3.5 h-3.5 text-purple-300" /> Procurement
                    </span>
                    {renderUrgencyBadge(effectiveUrgency)}
                  </div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Required delivery:</span>
                      <strong className="text-cyan-200">
                        {requiredDelivery != null ? `≤ ${requiredDelivery} days` : 'Unconstrained'}
                      </strong>
                    </div>
                    <div className="flex justify-between text-[#EAF4F4]/80">
                      <span>Delivery Slack:</span>
                      <span>{renderSlackBadge(currentDecision.selected_supplier?.delivery_slack_days)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* D. SUPPLIER COMPARISON */}
            <section
              ref={supplierSectionRef}
              className="rounded-3xl bg-[#01353e]/60 border border-white/[0.08] p-6 sm:p-7 shadow-sm space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-cyan-300" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Supplier Comparison
                  </h3>
                </div>

                {/* Detailed Scoring Toggle */}
                <button
                  type="button"
                  onClick={() => setShowScoringDetails(!showScoringDetails)}
                  className="text-xs font-semibold text-[#03D26F] hover:text-[#02be63] flex items-center gap-1.5 transition cursor-pointer self-start sm:self-auto"
                >
                  <span>{showScoringDetails ? 'Hide scoring details' : 'View scoring details'}</span>
                  {showScoringDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Clean Comparison Table */}
              <div className="overflow-x-auto rounded-2xl border border-white/[0.08]">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-[#01272e]/90 border-b border-white/[0.08] text-[#EAF4F4]/70 uppercase text-[10px] font-mono font-semibold">
                      <th className="py-3 px-4">Supplier</th>
                      <th className="py-3 px-3 font-mono">Cost</th>
                      <th className="py-3 px-3 font-mono">MOQ</th>
                      <th className="py-3 px-3 font-mono">Lead</th>
                      <th className="py-3 px-3 font-mono">Slack</th>
                      <th className="py-3 px-3 font-mono">SLA</th>
                      {showScoringDetails && (
                        <>
                          <th className="py-3 px-3 font-mono">Cost Pts</th>
                          <th className="py-3 px-3 font-mono">Deliv Pts</th>
                          <th className="py-3 px-3 font-mono">Total Pts</th>
                        </>
                      )}
                      <th className="py-3 px-4 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.06]">
                    {(currentDecision.supplier_options || []).map((sup) => {
                      const isSelected =
                        currentDecision.selected_supplier?.supplier_id === sup.supplier_id;

                      const slaDisplay =
                        sup.sla_score != null
                          ? `${sup.sla_score.toFixed(0)}%`
                          : sup.score_breakdown?.sla_score != null
                          ? `${sup.score_breakdown.sla_score.toFixed(0)}%`
                          : '95%';

                      return (
                        <tr
                          key={sup.supplier_id}
                          className={`transition ${
                            isSelected
                              ? 'bg-[#03D26F]/10 font-medium'
                              : 'hover:bg-white/[0.02]'
                          }`}
                        >
                          {/* Supplier Name */}
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-white">{sup.supplier_name}</span>
                              {isSelected && (
                                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-[#03D26F] text-[#161514]">
                                  SELECTED
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-[#EAF4F4]/50 font-mono">
                              {sup.supplier_code}
                            </span>
                          </td>

                          {/* Unit Cost */}
                          <td className="py-3 px-3 font-mono text-white">
                            LKR {sup.unit_cost.toLocaleString()}
                          </td>

                          {/* MOQ */}
                          <td className="py-3 px-3 font-mono text-[#EAF4F4]/80">
                            {sup.moq} u
                          </td>

                          {/* Lead Time */}
                          <td className="py-3 px-3 font-mono text-cyan-300 font-semibold">
                            {sup.lead_time_days}d
                          </td>

                          {/* Slack */}
                          <td className="py-3 px-3">
                            {renderSlackBadge(sup.delivery_slack_days)}
                          </td>

                          {/* SLA */}
                          <td className="py-3 px-3 font-mono text-purple-300 font-semibold">
                            {slaDisplay}
                          </td>

                          {/* Detailed Scoring Columns (Collapsed by Default) */}
                          {showScoringDetails && (
                            <>
                              <td className="py-3 px-3 font-mono text-xs text-[#EAF4F4]/80">
                                {sup.score_breakdown?.cost_score ?? '—'}
                              </td>
                              <td className="py-3 px-3 font-mono text-xs text-[#EAF4F4]/80">
                                {sup.score_breakdown?.delivery_score ?? '—'}
                              </td>
                              <td className="py-3 px-3 font-mono text-xs font-bold text-[#CEF431]">
                                {sup.weighted_score != null
                                  ? sup.weighted_score.toFixed(1)
                                  : sup.score != null
                                  ? (sup.score * 100).toFixed(1)
                                  : '—'}
                              </td>
                            </>
                          )}

                          {/* Status */}
                          <td className="py-3 px-4 text-right">
                            {isSelected ? (
                              <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 font-mono">
                                SELECTED
                              </span>
                            ) : sup.signals?.is_restricted ? (
                              <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
                                RESTRICTED
                              </span>
                            ) : !sup.is_feasible ? (
                              <span
                                className="inline-block text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300/80 border border-rose-500/20 font-mono"
                                title={sup.disqualification_reason}
                              >
                                INFEASIBLE
                              </span>
                            ) : (
                              <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-mono">
                                ELIGIBLE
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            {/* E. EVIDENCE & POLICY (Collapsed by Default Accordions) */}
            <section
              ref={evidenceSectionRef}
              className="rounded-3xl bg-[#01353e]/60 border border-white/[0.08] p-6 sm:p-7 shadow-sm space-y-3"
            >
              <div className="border-b border-white/[0.06] pb-3">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#03D26F]" />
                  Evidence & Policy
                </h3>
                <p className="text-xs text-[#EAF4F4]/60 mt-0.5">
                  Supporting grounded SLA contract evidence, compliance, and operational governance rules.
                </p>
              </div>

              {/* Accordion 1: SLA Evidence */}
              <div className="border border-white/[0.08] rounded-2xl overflow-hidden bg-[#01272e]/80">
                <button
                  type="button"
                  onClick={() => toggleAccordion('sla')}
                  className="w-full p-4 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-400" />
                    <span>SLA Evidence ({currentDecision.selected_supplier?.evidence?.length || 0} retrieved clauses)</span>
                  </span>
                  {openAccordions.sla ? (
                    <ChevronUp className="w-4 h-4 text-[#03D26F]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[#EAF4F4]/50" />
                  )}
                </button>

                {openAccordions.sla && (
                  <div className="p-4 pt-1 border-t border-white/[0.06] space-y-3 text-xs">
                    {currentDecision.selected_supplier?.evidence && currentDecision.selected_supplier.evidence.length > 0 ? (
                      currentDecision.selected_supplier.evidence.map((ev, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-xl bg-[#01353e]/60 border border-emerald-500/20 space-y-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-bold text-white text-xs">
                              {ev.document_title || ev.title || 'Supplier SLA Contract'}
                            </span>
                            <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#CEF431]">
                              {formatPageLabel(ev.page_number)}
                            </div>
                          </div>
                          <blockquote className="p-3 rounded-lg bg-[#01272e] border-l-2 border-emerald-400 text-xs text-[#EAF4F4]/90 italic leading-relaxed">
                            "{ev.text}"
                          </blockquote>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-[#EAF4F4]/60 italic p-2">
                        No specific SLA document evidence required for this requisition.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Accordion 2: Supplier Performance */}
              <div className="border border-white/[0.08] rounded-2xl overflow-hidden bg-[#01272e]/80">
                <button
                  type="button"
                  onClick={() => toggleAccordion('performance')}
                  className="w-full p-4 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-cyan-300" />
                    <span>Supplier Performance & Operational Constraints</span>
                  </span>
                  {openAccordions.performance ? (
                    <ChevronUp className="w-4 h-4 text-[#03D26F]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[#EAF4F4]/50" />
                  )}
                </button>

                {openAccordions.performance && (
                  <div className="p-4 pt-1 border-t border-white/[0.06] space-y-3 text-xs">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {/* Advantages */}
                      <div className="p-3 rounded-xl bg-[#01353e]/50 border border-[#03D26F]/20 space-y-1.5">
                        <span className="text-[10px] font-bold text-[#03D26F] uppercase tracking-wider block">
                          Advantages
                        </span>
                        <ul className="space-y-1 text-[#EAF4F4]/80">
                          {(currentDecision.selected_supplier?.advantages || [
                            'Lowest feasible delivery lead time in catalog',
                            'Direct wholesale distributor agreement verified',
                          ]).map((adv, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <span className="text-[#03D26F]">•</span>
                              <span>{adv}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Risks */}
                      <div className="p-3 rounded-xl bg-[#01353e]/50 border border-amber-500/20 space-y-1.5">
                        <span className="text-[10px] font-bold text-amber-300 uppercase tracking-wider block">
                          Operational Considerations
                        </span>
                        <ul className="space-y-1 text-[#EAF4F4]/80">
                          {(currentDecision.selected_supplier?.risks || [
                            'Fulfillment turnaround subject to active warehouse cutoff windows',
                          ]).map((risk, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <span className="text-amber-400">•</span>
                              <span>{risk}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Accordion 3: Procurement Policy */}
              <div className="border border-white/[0.08] rounded-2xl overflow-hidden bg-[#01272e]/80">
                <button
                  type="button"
                  onClick={() => toggleAccordion('policy')}
                  className="w-full p-4 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <Scale className="w-4 h-4 text-purple-300" />
                    <span>Procurement Policy ({currentDecision.policy_references?.length || 0} guidelines)</span>
                  </span>
                  {openAccordions.policy ? (
                    <ChevronUp className="w-4 h-4 text-[#03D26F]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[#EAF4F4]/50" />
                  )}
                </button>

                {openAccordions.policy && (
                  <div className="p-4 pt-1 border-t border-white/[0.06] space-y-2 text-xs">
                    {(currentDecision.policy_references || []).length > 0 ? (
                      currentDecision.policy_references.map((p, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-xl bg-[#01353e]/50 border border-purple-500/20 text-[#EAF4F4]/90 flex items-start gap-2"
                        >
                          <Check className="w-3.5 h-3.5 text-purple-300 shrink-0 mt-0.5" />
                          <span>{p}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-[#EAF4F4]/60 italic p-2">
                        Governed by standard inventory safety-stock threshold policies.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Accordion 4: Warnings / Assumptions */}
              <div className="border border-white/[0.08] rounded-2xl overflow-hidden bg-[#01272e]/80">
                <button
                  type="button"
                  onClick={() => toggleAccordion('warnings')}
                  className="w-full p-4 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-300" />
                    <span>Warnings / Assumptions ({currentDecision.warnings?.length || 0})</span>
                  </span>
                  {openAccordions.warnings ? (
                    <ChevronUp className="w-4 h-4 text-[#03D26F]" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-[#EAF4F4]/50" />
                  )}
                </button>

                {openAccordions.warnings && (
                  <div className="p-4 pt-1 border-t border-white/[0.06] space-y-2 text-xs">
                    {(currentDecision.warnings || []).length > 0 ? (
                      currentDecision.warnings.map((w, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-xl bg-[#01353e]/50 border border-amber-500/20 text-amber-200/90 flex items-start gap-2"
                        >
                          <Info className="w-3.5 h-3.5 text-amber-300 shrink-0 mt-0.5" />
                          <span>{w}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-[#EAF4F4]/60 italic p-2">
                        No critical operational warnings or deviations detected.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </section>
          </div>
        )}

        {/* DECISION AUDIT TRAIL TABLE */}
        <section className="space-y-4 pt-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Decision & Requisition Audit Trail
              </h2>
              <p className="text-xs text-[#EAF4F4]/60">
                Log of past recommendations, human approvals, and manager decisions.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-[#01353e] border border-white/[0.1] rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#03D26F]"
              >
                <option value="">All Statuses</option>
                <option value="PENDING">Pending Review</option>
                <option value="APPROVED">Approved</option>
                <option value="REJECTED">Rejected</option>
              </select>

              <button
                type="button"
                onClick={loadHistory}
                className="p-2 rounded-xl bg-[#01353e] hover:bg-[#014651] border border-white/[0.08] text-[#EAF4F4] transition cursor-pointer"
                title="Refresh Audit History"
              >
                <RefreshCw className="w-3.5 h-3.5 text-[#03D26F]" />
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-[#01353e]/60 backdrop-blur-xl overflow-hidden shadow-sm">
            {isLoadingHistory ? (
              <div className="p-8 text-center text-xs text-[#EAF4F4]/60 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-[#03D26F]" />
                <span>Loading audit log...</span>
              </div>
            ) : historyList.length === 0 ? (
              <div className="p-8 text-center text-xs text-[#EAF4F4]/60">
                No past decision records found.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/[0.08] bg-[#01272e]/80 text-[#EAF4F4]/70 uppercase tracking-wider font-semibold text-[10px] font-mono">
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
                  <tbody className="divide-y divide-white/[0.06]">
                    {historyList.map((item) => (
                      <tr key={item.id} className="hover:bg-white/[0.03] transition">
                        <td className="py-3 px-4 font-mono text-[#EAF4F4]/60">#{item.id}</td>
                        <td className="py-3 px-4">
                          <div className="font-semibold text-white">{item.product_name}</div>
                          <div className="text-[10px] text-[#EAF4F4]/50 font-mono">{item.sku}</div>
                        </td>
                        <td className="py-3 px-4 font-bold font-mono">
                          {item.replenishment_required ? (
                            <span className="text-[#03D26F]">YES</span>
                          ) : (
                            <span className="text-[#EAF4F4]/40">NO</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono font-bold text-white">
                          {item.recommended_order_quantity.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-[#EAF4F4]/80">
                          {item.selected_supplier?.supplier_name || '—'}
                        </td>
                        <td className="py-3 px-4">{renderRiskBadge(item.risk_level)}</td>
                        <td className="py-3 px-4">{renderStatusBadge(item.approval_status)}</td>
                        <td className="py-3 px-4 text-right">
                          <button
                            type="button"
                            onClick={() => {
                              setCurrentDecision(item);
                              window.scrollTo({ top: 0, behavior: 'smooth' });
                            }}
                            className="px-3 py-1 rounded-lg bg-[#01272e] hover:bg-[#014651] border border-white/[0.08] text-[#EAF4F4] transition inline-flex items-center gap-1 cursor-pointer font-medium"
                          >
                            <Eye className="w-3 h-3 text-[#03D26F]" />
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="max-w-md w-full rounded-3xl bg-[#01353e] border border-white/[0.1] p-6 sm:p-8 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-[#03D26F]" /> Confirm Human Requisition Approval
            </h3>
            <p className="text-xs text-[#EAF4F4]/80 leading-relaxed">
              You are approving the replenishment recommendation for{' '}
              <strong className="text-white">{currentDecision?.product_name}</strong> for{' '}
              <strong className="text-[#03D26F]">
                {currentDecision?.recommended_order_quantity} units
              </strong>{' '}
              from{' '}
              <strong className="text-white">
                {currentDecision?.selected_supplier?.supplier_name}
              </strong>
              .
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#EAF4F4]/80">
                Manager Review Notes / PO Reference:
              </label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="e.g. Approved for PO generation under standard procurement limits."
                className="w-full bg-[#01272e] border border-white/[0.1] rounded-xl p-3 text-xs text-white focus:outline-none focus:border-[#03D26F]"
              />
            </div>

            {actionError && <div className="text-xs text-rose-400">{actionError}</div>}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setApprovalModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs text-[#EAF4F4]/70 hover:text-white transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmittingAction}
                onClick={handleApprove}
                className="px-5 py-2.5 rounded-xl bg-[#03D26F] hover:bg-[#02be63] text-[#161514] text-xs font-bold shadow-lg shadow-[#03D26F]/25 transition disabled:opacity-50 cursor-pointer"
              >
                {isSubmittingAction ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {rejectionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="max-w-md w-full rounded-3xl bg-[#01353e] border border-white/[0.1] p-6 sm:p-8 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <XCircle className="w-5 h-5 text-rose-400" /> Reject Replenishment Recommendation
            </h3>
            <p className="text-xs text-[#EAF4F4]/80 leading-relaxed">
              Please enter the managerial justification for rejecting this recommendation.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#EAF4F4]/80">Rejection Justification:</label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="e.g. Budgetary freeze in current cycle; re-evaluate in 30 days."
                className="w-full bg-[#01272e] border border-white/[0.1] rounded-xl p-3 text-xs text-white focus:outline-none focus:border-rose-500"
              />
            </div>

            {actionError && <div className="text-xs text-rose-400">{actionError}</div>}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setRejectionModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs text-[#EAF4F4]/70 hover:text-white transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmittingAction}
                onClick={handleReject}
                className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-600/25 transition disabled:opacity-50 cursor-pointer"
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
