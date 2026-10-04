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
  Cpu,
  ShieldAlert,
  ArrowUpRight,
  UserCheck,
  FileText,
  Quote,
  ChevronDown,
  ChevronUp,
  Scale,
  Database,
  Building2,
  Check,
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

  // Accordion state for candidate supplier evidence
  const [expandedSuppliers, setExpandedSuppliers] = useState({});

  const toggleSupplierEvidence = (supplierId) => {
    setExpandedSuppliers((prev) => ({
      ...prev,
      [supplierId]: !prev[supplierId],
    }));
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

  // Safe page number formatter (Never show "Page null")
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
    if (slack === null || slack === undefined) return null;
    if (slack > 0) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
          +{slack}d (Positive Margin)
        </span>
      );
    } else if (slack === 0) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/40">
          ⚠️ 0d (Critical / Zero Margin)
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/30">
          ❌ {slack}d (Infeasible)
        </span>
      );
    }
  };

  // Derive selected supplier candidate option and advantages/risks
  const selectedSupplierOption = useMemo(() => {
    if (!currentDecision?.selected_supplier?.supplier_id) return null;
    return (
      currentDecision.supplier_options?.find(
        (s) => s.supplier_id === currentDecision.selected_supplier.supplier_id
      ) || null
    );
  }, [currentDecision]);

  const selectedSupplierAdvantages = useMemo(() => {
    if (currentDecision?.selected_supplier?.advantages?.length) {
      return currentDecision.selected_supplier.advantages;
    }
    return selectedSupplierOption?.advantages || [];
  }, [currentDecision, selectedSupplierOption]);

  const selectedSupplierRisks = useMemo(() => {
    if (currentDecision?.selected_supplier?.risks?.length) {
      return currentDecision.selected_supplier.risks;
    }
    return selectedSupplierOption?.risks || [];
  }, [currentDecision, selectedSupplierOption]);

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col font-sans selection:bg-[#03D26F]/30 selection:text-white">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Header Hero Banner with Decision Hero Asset */}
        <section className="relative overflow-hidden rounded-3xl bg-[#01353e] border border-white/[0.1] p-6 sm:p-8 shadow-xl">
          <div
            className="absolute inset-0 bg-cover bg-center opacity-25 mix-blend-luminosity scale-105 pointer-events-none"
            style={{ backgroundImage: `url('/assets/decision-hero.jpg')` }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#01272e] via-[#01353e]/90 to-[#014651]/85 pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-3 max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-[#03D26F]/15 border border-[#03D26F]/30 text-[#03D26F]">
                  <Sparkles className="w-3.5 h-3.5" />
                  Autonomous Synthesis Engine
                </span>
                <span className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-[#CEF431]/15 text-[#CEF431] border border-[#CEF431]/25 font-bold">
                  Member 4 • Grok AI LLM
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-white">
                Replenishment Decision Agent
              </h1>
              <p className="text-xs sm:text-sm text-[#EAF4F4]/80 leading-relaxed">
                Autonomous consensus synthesis uniting live warehouse telemetry, statistical demand volatility, and supplier SLA contracts into verified replenishment requisitions.
              </p>
            </div>

            {/* Role indicator chip */}
            <div className="shrink-0 bg-[#01272e]/80 border border-white/[0.1] p-3.5 rounded-2xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#03D26F] to-[#014651] flex items-center justify-center">
                {isAdmin ? <ShieldCheck className="w-4 h-4 text-white" /> : <UserCheck className="w-4 h-4 text-white" />}
              </div>
              <div className="text-xs">
                <span className="text-[#EAF4F4]/60 block text-[10px] uppercase font-mono">Workspace Role</span>
                <span className="font-bold text-white font-mono">{user?.role}</span>
                <span className="text-[10px] text-[#CEF431] block">
                  {isAdmin ? 'Full Approval Authority' : 'Recommendation View Only'}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Multi-Agent Connected Workflow Pipeline Visual */}
        <section className="bg-[#01353e]/40 border border-white/[0.08] rounded-2xl p-5 shadow-sm">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#EAF4F4]/60 mb-3 flex items-center justify-between">
            <span>Autonomous Multi-Agent Processing Pipeline</span>
            <span className="text-[#03D26F] font-semibold">Active Consensus Workflow</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Agent 1 */}
            <div className="p-3.5 rounded-xl bg-[#01272e]/80 border border-white/[0.06] flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-[#03D26F]/15 text-[#03D26F] flex items-center justify-center shrink-0 mt-0.5">
                <Boxes className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-mono text-[#03D26F] block font-semibold">AGENT 1</span>
                <p className="text-xs font-bold text-white truncate">Inventory Agent</p>
                <p className="text-[10px] text-[#EAF4F4]/60 mt-0.5">Physical Stock, ROP, Reserved Units</p>
              </div>
            </div>

            {/* Agent 2 */}
            <div className="p-3.5 rounded-xl bg-[#01272e]/80 border border-white/[0.06] flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-cyan-500/15 text-cyan-300 flex items-center justify-center shrink-0 mt-0.5">
                <TrendingUp className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-mono text-cyan-300 block font-semibold">AGENT 2</span>
                <p className="text-xs font-bold text-white truncate">Demand & Risk Agent</p>
                <p className="text-[10px] text-[#EAF4F4]/60 mt-0.5">SMA/EMA Trend, Stockout Probability</p>
              </div>
            </div>

            {/* Agent 3 */}
            <div className="p-3.5 rounded-xl bg-[#01272e]/80 border border-white/[0.06] flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-sky-500/15 text-sky-300 flex items-center justify-center shrink-0 mt-0.5">
                <Truck className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-mono text-sky-300 block font-semibold">AGENT 3</span>
                <p className="text-xs font-bold text-white truncate">Supplier & Policy</p>
                <p className="text-[10px] text-[#EAF4F4]/60 mt-0.5">MOQ, Lead Times, SLA Compliance</p>
              </div>
            </div>

            {/* Agent 4 */}
            <div className="p-3.5 rounded-xl bg-[#01272e]/90 border border-[#03D26F]/30 flex items-start gap-3 shadow-sm">
              <div className="w-7 h-7 rounded-lg bg-[#CEF431]/20 text-[#CEF431] flex items-center justify-center shrink-0 mt-0.5">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-mono text-[#CEF431] block font-semibold">AGENT 4 • CORE</span>
                <p className="text-xs font-bold text-white truncate">Decision Agent (Grok)</p>
                <p className="text-[10px] text-[#EAF4F4]/60 mt-0.5">Synthesis, Rationale, RBAC Guard</p>
              </div>
            </div>
          </div>
        </section>

        {/* Interactive Analyzer Panel */}
        <section className="p-6 sm:p-8 rounded-3xl bg-[#01353e]/60 border border-white/[0.1] backdrop-blur-xl space-y-6 shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <h2 className="text-sm font-bold uppercase tracking-wider text-[#EAF4F4] flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#03D26F]" /> Decision Input Parameters
            </h2>
            <span className="text-xs text-[#EAF4F4]/50 font-mono">Real-Time Synthesis Query</span>
          </div>

          <form onSubmit={handleGenerateDecision} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Target Catalog Product */}
              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-[#EAF4F4]/80">Target Catalog Product</label>
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value)}
                  className="w-full bg-[#01272e]/90 border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/30"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id} className="bg-[#01272e] text-white">
                      {p.name} ({p.sku}) • ROP: {p.reorder_point} units
                    </option>
                  ))}
                </select>
              </div>

              {/* Forecast Horizon */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[#EAF4F4]/80">Forecast Horizon</label>
                <select
                  value={forecastHorizon}
                  onChange={(e) => setForecastHorizon(Number(e.target.value))}
                  className="w-full bg-[#01272e]/90 border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/30"
                >
                  <option value={7} className="bg-[#01272e] text-white">7 Days (Short Term)</option>
                  <option value={14} className="bg-[#01272e] text-white">14 Days (Standard)</option>
                  <option value={30} className="bg-[#01272e] text-white">30 Days (Monthly)</option>
                </select>
              </div>
            </div>

            {/* Collapsible Advanced Options for Urgency Override */}
            <div className="pt-1">
              <button
                type="button"
                onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                className="text-xs font-semibold text-[#03D26F] hover:text-[#02be63] flex items-center gap-1.5 transition cursor-pointer"
              >
                {showAdvancedOptions ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                <span>{showAdvancedOptions ? 'Hide Advanced Options' : 'Advanced Options (Manual Urgency Override)'}</span>
              </button>

              {showAdvancedOptions && (
                <div className="mt-3 p-4 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-[#EAF4F4]/90 flex items-center gap-1.5">
                        <span>Urgency Override</span>
                        <span className="text-[10px] font-mono text-amber-300 bg-amber-500/15 px-1.5 py-0.2 rounded border border-amber-500/30">Audited</span>
                      </label>
                      <select
                        value={urgencyOverride}
                        onChange={(e) => setUrgencyOverride(e.target.value)}
                        className="w-full bg-[#01353e]/90 border border-white/[0.1] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#03D26F]"
                      >
                        <option value="auto">Auto-detect (Recommended — derived from inventory, forecast & lead times)</option>
                        <option value="normal">Normal (Cost Priority: 60% Cost, 20% Delivery, 20% SLA)</option>
                        <option value="high">High (Balanced: 40% Delivery, 40% Cost, 20% SLA)</option>
                        <option value="emergency">Emergency (Expedited: 60% Delivery, 25% SLA, 15% Cost)</option>
                      </select>
                    </div>
                    <div className="text-[11px] text-[#EAF4F4]/60 flex items-center">
                      Urgency is normally derived autonomously from warehouse trajectory and delivery feasibility window. Applying a manual override records an audit trail.
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Run Action Bar */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2">
              <div className="text-xs text-[#EAF4F4]/70">
                {selectedProduct && (
                  <span>
                    Evaluating: <strong className="text-white font-semibold">{selectedProduct.name}</strong> • SKU:{' '}
                    <code className="text-[#CEF431] font-mono">{selectedProduct.sku}</code>
                  </span>
                )}
              </div>

              <button
                type="submit"
                disabled={isGenerating || !selectedProductId}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-[#03D26F] hover:bg-[#02be63] text-[#161514] text-xs font-bold shadow-lg shadow-[#03D26F]/25 disabled:opacity-50 transition cursor-pointer"
              >
                {isGenerating ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#161514]" />
                    <span>Synthesizing Multi-Agents...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-[#161514]" />
                    <span>Run Decision Agent</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {agentError && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{agentError}</span>
            </div>
          )}
        </section>

        {/* Active Recommendation Output Card */}
        {currentDecision && (
          <section className="rounded-3xl bg-[#01353e]/80 border border-[#03D26F]/30 overflow-hidden shadow-2xl space-y-6">
            {/* Top Banner with Decision Status & RBAC Supervised Actions */}
            <div className="p-6 sm:p-8 bg-[#014651]/80 border-b border-white/[0.08] flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-xs text-[#EAF4F4]/70 uppercase tracking-wider font-semibold">
                    Decision Analysis Result
                  </span>
                  {renderStatusBadge(currentDecision.approval_status)}
                  {renderRiskBadge(currentDecision.risk_level)}
                </div>
                <h2 className="text-xl sm:text-2xl font-bold text-white mt-1.5">
                  {currentDecision.product_name}{' '}
                  <span className="text-xs font-mono font-normal text-[#EAF4F4]/60">
                    ({currentDecision.sku})
                  </span>
                </h2>
              </div>

              {/* Action Buttons for Human Approval (Admin Only RBAC) */}
              {currentDecision.approval_status === 'PENDING' && (
                isAdmin ? (
                  <div className="flex items-center gap-2.5">
                    <button
                      onClick={() => {
                        setActionNotes('');
                        setRejectionModalOpen(true);
                      }}
                      className="px-4 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 text-xs font-semibold transition cursor-pointer"
                    >
                      Reject Recommendation
                    </button>
                    <button
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
                  <div className="text-xs text-[#EAF4F4]/80 flex items-center gap-2 bg-[#01272e]/80 px-4 py-2 rounded-xl border border-white/[0.08]">
                    <Clock className="w-3.5 h-3.5 text-[#CEF431]" />
                    <span className="font-medium">Pending Administrator Review & Decision</span>
                  </div>
                )
              )}
            </div>

            {/* DETECTED PROCUREMENT CONDITION CARD */}
            {currentDecision.detected_condition && (
              <div className="mx-6 sm:mx-8 p-5 rounded-2xl bg-gradient-to-br from-[#01272e] via-[#01353e] to-[#014651]/70 border border-cyan-500/40 shadow-xl space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center">
                      <Cpu className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                        Detected Procurement Condition
                      </h3>
                      <p className="text-[10px] text-[#EAF4F4]/60">
                        Autonomous derivation from physical inventory trajectory, forecast velocity, and vendor lead times
                      </p>
                    </div>
                  </div>
                  {currentDecision.detected_condition.manual_override_applied && (
                    <span className="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase tracking-wide">
                      ⚠️ Manually Overridden (Audited)
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  {/* Risk Level */}
                  <div className="p-3 bg-[#01272e]/80 rounded-xl border border-white/[0.06]">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase block">Risk Level</span>
                    <div className="mt-1">{renderRiskBadge(currentDecision.detected_condition.risk_level || currentDecision.detected_condition.stockout_risk)}</div>
                  </div>

                  {/* Derived Urgency */}
                  <div className="p-3 bg-[#01272e]/80 rounded-xl border border-white/[0.06]">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase block">Derived Urgency</span>
                    <span className="text-sm font-bold font-mono uppercase text-white mt-1 block">
                      {currentDecision.detected_condition.derived_urgency || currentDecision.detected_condition.procurement_urgency}
                    </span>
                  </div>

                  {/* Effective Urgency */}
                  <div className="p-3 bg-[#01272e]/80 rounded-xl border border-white/[0.06]">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase block">Effective Urgency</span>
                    <span className="text-sm font-bold font-mono uppercase text-[#03D26F] mt-1 block">
                      {currentDecision.detected_condition.effective_urgency}
                    </span>
                  </div>

                  {/* Required Delivery Window */}
                  <div className="p-3 bg-[#01272e]/80 rounded-xl border border-cyan-500/30 bg-cyan-950/20">
                    <span className="text-cyan-300 text-[10px] font-semibold uppercase block">Required Delivery Window</span>
                    <span className="text-sm font-bold font-mono text-cyan-200 mt-1 block">
                      {currentDecision.detected_condition.required_delivery_window_days !== null
                        ? `≤ ${currentDecision.detected_condition.required_delivery_window_days} Days`
                        : 'Unconstrained'}
                    </span>
                  </div>
                </div>

                {/* Inventory Timing Horizon Grid: Distinguishing Buffer Breach from Available Inventory Exhaustion */}
                <div className="p-3.5 bg-[#01272e]/90 rounded-xl border border-white/[0.08] space-y-2">
                  <div className="text-[10px] font-mono uppercase font-bold text-[#CEF431] flex items-center gap-1.5">
                    <Clock className="w-3 h-3 text-[#CEF431]" />
                    <span>Inventory Timing Horizons</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                    <div className="p-2.5 rounded-lg bg-[#01353e]/40 border border-white/[0.06]">
                      <span className="text-[#EAF4F4]/60 text-[10px] block">BUFFER BREACH</span>
                      <span className="text-white font-bold text-sm block mt-0.5">
                        {currentDecision.detected_condition.days_until_buffer_breach !== null && currentDecision.detected_condition.days_until_buffer_breach !== undefined
                          ? `${currentDecision.detected_condition.days_until_buffer_breach} days`
                          : currentDecision.detected_condition.days_until_unsafe !== null
                          ? `${currentDecision.detected_condition.days_until_unsafe} days`
                          : 'No breach in horizon'}
                      </span>
                      <span className="text-[9px] text-[#EAF4F4]/50 block mt-0.5">Projected ROP buffer breach</span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-[#01353e]/40 border border-white/[0.06]">
                      <span className="text-[#EAF4F4]/60 text-[10px] block">AVAILABLE INVENTORY EXHAUSTION</span>
                      <span className="text-rose-300 font-bold text-sm block mt-0.5">
                        {currentDecision.detected_condition.days_until_stockout !== null && currentDecision.detected_condition.days_until_stockout !== undefined
                          ? `${currentDecision.detected_condition.days_until_stockout} days`
                          : 'No stockout in horizon'}
                      </span>
                      <span className="text-[9px] text-[#EAF4F4]/50 block mt-0.5">Available-to-fulfil stock exhaustion (≤ 0)</span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-[#01353e]/40 border border-cyan-500/25">
                      <span className="text-cyan-300 text-[10px] block">REQUIRED DELIVERY</span>
                      <span className="text-cyan-200 font-bold text-sm block mt-0.5">
                        ≤ {currentDecision.detected_condition.required_delivery_window_days} days
                      </span>
                      <span className="text-[9px] text-cyan-400/70 block mt-0.5">Governing arrival deadline</span>
                    </div>
                  </div>
                </div>

                {/* Condition Rationale & Scoring Weights */}
                <div className="p-3.5 rounded-xl bg-[#01272e]/90 border border-white/[0.06] text-xs space-y-2">
                  <div className="text-[11px] text-[#EAF4F4]/90 leading-relaxed">
                    <strong className="text-[#03D26F]">Condition Reason: </strong>
                    {currentDecision.detected_condition.condition_reason || currentDecision.detected_condition.reason}
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] font-mono text-[#EAF4F4]/70 pt-2 border-t border-white/[0.06]">
                    <span>
                      Situation Scoring Weights: <strong className="text-white">{(currentDecision.detected_condition.weight_cost * 100).toFixed(0)}% Cost</strong> • <strong className="text-white">{(currentDecision.detected_condition.weight_delivery * 100).toFixed(0)}% Delivery</strong> • <strong className="text-white">{(currentDecision.detected_condition.weight_sla * 100).toFixed(0)}% SLA</strong>
                    </span>
                    {currentDecision.detected_condition.governing_policy_doc && (
                      <span className="text-purple-300">
                        Governing Policy: {currentDecision.detected_condition.governing_policy_doc}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Core Outputs Triad Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 px-6 sm:px-8">
              {/* Output 1: Replenishment Required */}
              <div className="p-5 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-2">
                <span className="text-[11px] text-[#EAF4F4]/70 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                  <Boxes className="w-3.5 h-3.5 text-[#03D26F]" /> Replenishment Required
                </span>
                <div className="flex items-baseline gap-2.5">
                  <span
                    className={`text-3xl font-black tracking-tight ${
                      currentDecision.replenishment_required ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'
                    }`}
                  >
                    {currentDecision.replenishment_required ? 'YES' : 'NO'}
                  </span>
                  <span className="text-xs text-[#EAF4F4]/70">
                    {currentDecision.replenishment_required ? 'Restock order triggered' : 'Inventory adequate'}
                  </span>
                </div>
              </div>

              {/* Output 2: Recommended Order Quantity */}
              <div className="p-5 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-2">
                <span className="text-[11px] text-[#EAF4F4]/70 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-[#CEF431]" /> Recommended Order Quantity
                </span>
                <div className="flex items-baseline gap-2.5">
                  <span className="text-3xl font-black text-white tracking-tight font-mono">
                    {currentDecision.recommended_order_quantity.toLocaleString()}
                  </span>
                  <span className="text-xs text-[#EAF4F4]/70">units (clamped non-negative)</span>
                </div>
              </div>

              {/* Output 3: Recommended Supplier */}
              <div className="p-5 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-2">
                <span className="text-[11px] text-[#EAF4F4]/70 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                  <Truck className="w-3.5 h-3.5 text-cyan-300" /> Designated Supplier
                </span>
                {currentDecision.selected_supplier ? (
                  <div>
                    <div className="text-base font-bold text-white truncate">
                      {currentDecision.selected_supplier.supplier_name}
                    </div>
                    <div className="text-[11px] text-[#EAF4F4]/70 flex items-center gap-2 mt-1">
                      <span>LKR {currentDecision.selected_supplier.unit_cost.toLocaleString()} / unit</span>
                      <span>•</span>
                      <span>{currentDecision.selected_supplier.lead_time_days}d lead time</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-[#EAF4F4]/50 italic">None (No order required or no vendor)</div>
                )}
              </div>
            </div>

            {/* Visual Workflow Flow: "How this decision was made" */}
            <div className="mx-6 sm:mx-8 p-4 rounded-2xl bg-[#01272e]/90 border border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#EAF4F4]/80 flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                  <Layers className="w-3.5 h-3.5 text-[#03D26F]" /> How this decision was made
                </span>
                <span className="text-[10px] text-[#EAF4F4]/50 font-mono">5-Stage Consensus Pipeline</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
                {/* Step 1: Inventory */}
                <div className="p-2.5 rounded-xl bg-[#01353e]/50 border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-[#03D26F] font-mono font-bold">
                    <span>1. INVENTORY</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20 font-sans">Operational Data</span>
                  </div>
                  <p className="text-xs font-semibold text-white">Stock Position</p>
                  <p className="text-[10px] text-[#EAF4F4]/70 leading-tight">
                    Avail: {currentDecision.inventory_context?.available_stock ?? '-'} • Inbound: {currentDecision.inventory_context?.incoming ?? '-'}
                  </p>
                </div>

                {/* Step 2: Demand */}
                <div className="p-2.5 rounded-xl bg-[#01353e]/50 border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-cyan-300 font-mono font-bold">
                    <span>2. DEMAND & RISK</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20 font-sans">Operational Data</span>
                  </div>
                  <p className="text-xs font-semibold text-white">Forecast Volatility</p>
                  <p className="text-[10px] text-[#EAF4F4]/70 leading-tight">
                    {currentDecision.demand_context?.forecast_horizon_days ?? 14}d: {currentDecision.demand_context?.total_forecasted_demand ?? '-'}u • {currentDecision.risk_level}
                  </p>
                </div>

                {/* Step 3: Suppliers */}
                <div className="p-2.5 rounded-xl bg-[#01353e]/50 border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-sky-300 font-mono font-bold">
                    <span>3. SUPPLIERS</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20 font-sans">Operational Data</span>
                  </div>
                  <p className="text-xs font-semibold text-white">Commercial Eval</p>
                  <p className="text-[10px] text-[#EAF4F4]/70 leading-tight">
                    {currentDecision.supplier_options?.length || 0} active candidate offers evaluated
                  </p>
                </div>

                {/* Step 4: Document IR */}
                <div className="p-2.5 rounded-xl bg-[#01353e]/50 border border-emerald-500/30 space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-emerald-300 font-mono font-bold">
                    <span>4. DOCUMENT IR</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-sans font-bold">Document IR</span>
                  </div>
                  <p className="text-xs font-semibold text-white">SLA & Policies</p>
                  <p className="text-[10px] text-emerald-200/80 leading-tight">
                    Retrieved SLA & procurement clauses
                  </p>
                </div>

                {/* Step 5: Decision */}
                <div className="p-2.5 rounded-xl bg-[#01353e]/70 border border-[#03D26F]/40 space-y-1 shadow-sm">
                  <div className="flex items-center justify-between text-[10px] text-[#CEF431] font-mono font-bold">
                    <span>5. SYNTHESIS</span>
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-[#CEF431]/20 text-[#CEF431] border border-[#CEF431]/30 font-sans font-bold">Consensus</span>
                  </div>
                  <p className="text-xs font-semibold text-white">Requisition</p>
                  <p className="text-[10px] text-[#CEF431] leading-tight font-semibold">
                    {currentDecision.replenishment_required
                      ? `Reorder ${currentDecision.recommended_order_quantity} units`
                      : 'Stock sufficient'}
                  </p>
                </div>
              </div>
            </div>

            {/* SECTION 1: DECISION REASONING */}
            <div className="mx-6 sm:mx-8 p-6 rounded-2xl bg-[#01272e]/90 border border-[#03D26F]/30 space-y-5 shadow-lg">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.08] pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-[#03D26F]/15 text-[#03D26F] flex items-center justify-center">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                      Decision Reasoning
                    </h3>
                    <p className="text-[11px] text-[#EAF4F4]/60">
                      Authoritative inventory telemetry, demand volatility, and consensus replenishment formula
                    </p>
                  </div>
                </div>
                {currentDecision.confidence !== null && (
                  <span className="text-[#CEF431] font-mono text-[11px] font-bold bg-[#CEF431]/10 px-2.5 py-0.5 rounded-full border border-[#CEF431]/20">
                    Confidence: {(currentDecision.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              {/* Operational Factors Key-Value Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
                {/* Available Stock */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Available Stock</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                  </div>
                  <div className="text-lg font-black text-white font-mono">
                    {currentDecision.inventory_context?.available_stock ?? '-'} units
                  </div>
                  <div className="text-[10px] text-[#EAF4F4]/50">Physical on-hand minus reserved</div>
                </div>

                {/* Incoming Pipeline */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Incoming Pipeline</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                  </div>
                  <div className="text-lg font-black text-cyan-300 font-mono">
                    {currentDecision.inventory_context?.incoming ?? '-'} units
                  </div>
                  <div className="text-[10px] text-[#EAF4F4]/50">Confirmed inbound purchase orders</div>
                </div>

                {/* Effective Inventory */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-[#03D26F]/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#03D26F] text-[10px] font-semibold uppercase">Effective Inventory</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                  </div>
                  <div className="text-lg font-black text-[#03D26F] font-mono">
                    {currentDecision.inventory_context?.effective_inventory ??
                      ((currentDecision.inventory_context?.available_stock ?? 0) + (currentDecision.inventory_context?.incoming ?? 0))} units
                  </div>
                  <div className="text-[10px] text-[#03D26F]/80">Available stock + incoming pipeline</div>
                </div>

                {/* Forecast Demand */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Forecast Demand</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                  </div>
                  <div className="text-lg font-black text-white font-mono">
                    {currentDecision.demand_context?.total_forecasted_demand ?? '-'} units
                  </div>
                  <div className="text-[10px] text-[#EAF4F4]/50">Over {currentDecision.demand_context?.forecast_horizon_days ?? 14}-day horizon</div>
                </div>

                {/* ROP Buffer / Safety Stock */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">ROP Buffer</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                  </div>
                  <div className="text-lg font-black text-[#CEF431] font-mono">
                    {currentDecision.inventory_context?.reorder_point ?? '-'} units
                  </div>
                  <div className="text-[10px] text-[#EAF4F4]/50">Effective retained safety-stock buffer</div>
                </div>

                {/* Stockout Risk */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Stockout Risk</span>
                  </div>
                  <div className="mt-1">{renderRiskBadge(currentDecision.demand_context?.risk_level || currentDecision.risk_level)}</div>
                  <div className="text-[10px] text-[#EAF4F4]/50">Lead-time demand: {currentDecision.demand_context?.expected_demand_over_lead_time ?? '-'} units</div>
                </div>

                {/* Recommended Quantity */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-[#03D26F]/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#03D26F] text-[10px] font-semibold uppercase">Recommended Qty</span>
                  </div>
                  <div className="text-lg font-black text-[#03D26F] font-mono">
                    {currentDecision.recommended_order_quantity} units
                  </div>
                  <div className="text-[10px] text-[#03D26F]/80">Replenishment order quantity</div>
                </div>

                {/* Supplier MOQ */}
                <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Supplier MOQ</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                  </div>
                  <div className="text-lg font-black text-white font-mono">
                    {currentDecision.selected_supplier?.moq ? `${currentDecision.selected_supplier.moq} units` : 'N/A'}
                  </div>
                  <div className="text-[10px] text-[#EAF4F4]/50">Minimum batch constraint</div>
                </div>
              </div>

              {/* Grok AI Explainability Rationale */}
              <div className="p-4 rounded-xl bg-[#01353e]/70 border border-white/[0.08] space-y-2">
                <span className="text-[11px] font-bold text-[#03D26F] uppercase tracking-wider flex items-center gap-1.5">
                  <Quote className="w-3.5 h-3.5" /> Explainable Synthesis Narrative:
                </span>
                <p className="text-xs text-[#EAF4F4] leading-relaxed whitespace-pre-line font-normal">
                  {currentDecision.reasoning}
                </p>
              </div>

              {/* Strategic Factors Considered */}
              {currentDecision.factors && currentDecision.factors.length > 0 && (
                <div className="space-y-2 pt-1">
                  <h4 className="text-[11px] font-bold text-[#EAF4F4]/70 uppercase tracking-wider">
                    Key Factors Considered in Synthesis
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    {currentDecision.factors.map((factor, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded-xl bg-[#01353e]/40 border border-white/[0.06] text-[#EAF4F4]/90 flex items-start gap-2"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-[#03D26F] shrink-0 mt-0.5" />
                        <span className="leading-snug text-[11px]">{factor}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* SECTION 2: SELECTED SUPPLIER */}
            {currentDecision.selected_supplier ? (
              <div className="mx-6 sm:mx-8 p-6 rounded-2xl bg-[#01272e]/90 border border-cyan-500/30 space-y-6 shadow-lg">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-cyan-500/15 text-cyan-300 flex items-center justify-center">
                      <Truck className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-white">
                          Selected Supplier: {currentDecision.selected_supplier.supplier_name}
                        </h3>
                        {currentDecision.selected_supplier.supplier_code && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/[0.08] text-[#EAF4F4]/70">
                            {currentDecision.selected_supplier.supplier_code}
                          </span>
                        )}
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 font-mono">
                          Designated Optimal
                        </span>
                      </div>
                      <p className="text-[11px] text-[#EAF4F4]/60 mt-0.5">
                        Authoritative PostgreSQL commercial terms verified against active vendor catalogs
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-[10px] text-[#EAF4F4]/60 uppercase font-mono block">Estimated Spend</span>
                    <span className="text-base font-mono font-bold text-[#03D26F]">
                      LKR {currentDecision.selected_supplier.estimated_total_cost.toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Authoritative Commercial Terms Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Unit Cost</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                    </div>
                    <div className="text-base font-bold text-white font-mono">
                      LKR {currentDecision.selected_supplier.unit_cost.toLocaleString()}
                    </div>
                    <div className="text-[10px] text-[#EAF4F4]/50">Wholesale price per unit</div>
                  </div>

                  <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Minimum Order (MOQ)</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                    </div>
                    <div className="text-base font-bold text-white font-mono">
                      {currentDecision.selected_supplier.moq} units
                    </div>
                    <div className="text-[10px] text-[#EAF4F4]/50">Minimum batch constraint</div>
                  </div>

                  <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Delivery Lead Time</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                    </div>
                    <div className="text-base font-bold text-cyan-300 font-mono">
                      {currentDecision.selected_supplier.lead_time_days} days
                    </div>
                    <div className="text-[10px] text-[#EAF4F4]/50">Fulfillment turnaround</div>
                  </div>

                  <div className="p-3 bg-[#01353e]/60 rounded-xl border border-white/[0.06] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Total Order Spend</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sky-500/15 text-sky-300 border border-sky-500/20">Operational Data</span>
                    </div>
                    <div className="text-base font-bold text-[#03D26F] font-mono">
                      LKR {currentDecision.selected_supplier.estimated_total_cost.toLocaleString()}
                    </div>
                    <div className="text-[10px] text-[#EAF4F4]/50">unit_cost × recommended_qty</div>
                  </div>
                </div>

                {/* Selection Reason */}
                <div className="p-3.5 rounded-xl bg-[#01353e]/50 border border-white/[0.06] text-xs text-[#EAF4F4] leading-relaxed">
                  <span className="font-semibold text-cyan-300">Selection Justification: </span>
                  <span>{currentDecision.selected_supplier.selection_reason}</span>
                </div>

                {/* Why this supplier? (Advantages & Risks) */}
                <div className="space-y-3 pt-1 border-t border-white/[0.06]">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#03D26F]" /> Why this supplier?
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    {/* Advantages */}
                    <div className="p-4 rounded-xl bg-[#01353e]/40 border border-[#03D26F]/20 space-y-2">
                      <span className="text-[11px] font-bold text-[#03D26F] uppercase tracking-wider flex items-center gap-1.5">
                        <Check className="w-3.5 h-3.5" /> Key Advantages
                      </span>
                      {selectedSupplierAdvantages.length > 0 ? (
                        <ul className="space-y-1.5">
                          {selectedSupplierAdvantages.map((adv, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-[#EAF4F4]/90 text-[11px] leading-snug">
                              <span className="text-[#03D26F] font-bold mt-0.5">•</span>
                              <span>{adv}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-[11px] text-[#EAF4F4]/60 italic">
                          Cost-effective compliant active supplier meeting all operational thresholds.
                        </p>
                      )}
                    </div>

                    {/* Operational Risks */}
                    <div className="p-4 rounded-xl bg-[#01353e]/40 border border-amber-500/20 space-y-2">
                      <span className="text-[11px] font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" /> Operational Considerations & Risks
                      </span>
                      {selectedSupplierRisks.length > 0 ? (
                        <ul className="space-y-1.5">
                          {selectedSupplierRisks.map((risk, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-[#EAF4F4]/90 text-[11px] leading-snug">
                              <span className="text-amber-400 font-bold mt-0.5">•</span>
                              <span>{risk}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-[11px] text-[#EAF4F4]/60 italic">
                          No operational risks, penalty clauses, or compliance infractions identified.
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* SECTION 3: DOCUMENT IR EVIDENCE UNDER SELECTED SUPPLIER */}
                <div className="space-y-3 pt-2 border-t border-white/[0.06]">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-emerald-400" /> Document Evidence (IR Provenance)
                      </h4>
                      <p className="text-[11px] text-[#EAF4F4]/60 mt-0.5">
                        Authoritative SLA contracts & procurement policy clauses retrieved from knowledge base
                      </p>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      {currentDecision.selected_supplier.evidence?.length || 0} Grounded Chunks
                    </span>
                  </div>

                  {currentDecision.selected_supplier.evidence && currentDecision.selected_supplier.evidence.length > 0 ? (
                    <div className="grid grid-cols-1 gap-3">
                      {currentDecision.selected_supplier.evidence.map((ev, idx) => {
                        const pageLabel = formatPageLabel(ev.page_number);
                        const docType = formatDocumentType(ev.document_type);

                        return (
                          <div
                            key={idx}
                            className="p-4 rounded-xl bg-[#01353e]/60 border border-emerald-500/30 space-y-2.5 shadow-sm"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                                <span className="font-bold text-white text-xs truncate">
                                  {ev.document_title || ev.title || 'Supplier Document'}
                                </span>
                                <span className="text-[10px] text-[#EAF4F4]/60 font-mono">
                                  • {docType}
                                </span>
                                {pageLabel && (
                                  <span className="text-[10px] font-mono text-[#CEF431] font-semibold">
                                    • {pageLabel}
                                  </span>
                                )}
                                {ev.chunk_index !== null && ev.chunk_index !== undefined && (
                                  <span className="text-[10px] text-[#EAF4F4]/50 font-mono">
                                    • Chunk #{ev.chunk_index}
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center gap-1.5 shrink-0">
                                <span className="text-[9px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                  Document IR
                                </span>
                                <span className="text-[9px] font-mono font-semibold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                  Policy / SLA
                                </span>
                              </div>
                            </div>

                            <blockquote className="p-3 rounded-lg bg-[#01272e]/80 border-l-2 border-emerald-400 text-xs text-[#EAF4F4]/90 italic leading-relaxed">
                              "{ev.text}"
                            </blockquote>

                            {typeof ev.distance === 'number' && (
                              <div className="text-[10px] text-[#EAF4F4]/50 font-mono flex items-center justify-between pt-1">
                                <span>Authority: {ev.authority || 'policy_or_sla'}</span>
                                <span>Relevance Distance: {ev.distance.toFixed(4)} (Retrieval Relevance)</span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl bg-[#01353e]/40 border border-white/[0.06] text-xs text-[#EAF4F4]/60 text-center">
                      No document evidence was required or retrieved for this supplier.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* No replenishment required state */
              <div className="mx-6 sm:mx-8 p-6 rounded-2xl bg-[#01272e]/90 border border-emerald-500/30 space-y-2 text-center">
                <div className="inline-flex p-3 rounded-2xl bg-emerald-500/15 text-emerald-300 mb-1">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-white">No Replenishment Order Required</h3>
                <p className="text-xs text-[#EAF4F4]/80 max-w-xl mx-auto leading-relaxed">
                  Effective inventory is sufficient to cover forecast demand and retain the reorder-point safety buffer.
                  No vendor requisition or purchase order generation is necessary at this time.
                </p>
              </div>
            )}

            {/* SECTION 4: POLICY REFERENCES */}
            {currentDecision.policy_references && currentDecision.policy_references.length > 0 && (
              <div className="mx-6 sm:mx-8 p-5 rounded-2xl bg-[#01272e]/80 border border-purple-500/30 space-y-3 shadow-md">
                <div className="flex items-center gap-2 text-purple-300">
                  <Scale className="w-4 h-4" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                    Policy References
                  </h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                    Governance Rules
                  </span>
                </div>
                <p className="text-[11px] text-[#EAF4F4]/60">
                  Interpreted corporate procurement policies and financial threshold constraints governing this requisition:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {currentDecision.policy_references.map((policy, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-[#01353e]/60 border border-purple-500/20 text-[#EAF4F4] flex items-start gap-2.5"
                    >
                      <Check className="w-4 h-4 text-purple-300 shrink-0 mt-0.5" />
                      <span className="leading-snug">{policy}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* SECTION 5: ASSUMPTIONS & WARNINGS */}
            {currentDecision.warnings && currentDecision.warnings.length > 0 && (
              <div className="mx-6 sm:mx-8 p-5 rounded-2xl bg-[#01272e]/80 border border-amber-500/30 space-y-3 shadow-md">
                <div className="flex items-center gap-2 text-amber-300">
                  <AlertTriangle className="w-4 h-4" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                    Assumptions & Warnings
                  </h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    Operational Notices
                  </span>
                </div>
                <p className="text-[11px] text-[#EAF4F4]/60">
                  The following operational assumptions or model caveats apply to this recommendation:
                </p>
                <ul className="text-xs text-amber-200/90 space-y-2">
                  {currentDecision.warnings.map((w, idx) => (
                    <li key={idx} className="p-3 rounded-xl bg-[#01353e]/60 border border-amber-500/20 flex items-start gap-2.5">
                      <Info className="w-4 h-4 text-amber-300 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{w}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* SECTION 6: SUPPLIER CANDIDATES COMPARISON WITH ACCORDION EVIDENCE */}
            {currentDecision.supplier_options && currentDecision.supplier_options.length > 0 && (
              <div className="mx-6 sm:mx-8 p-6 rounded-2xl bg-[#01272e]/90 border border-white/[0.08] space-y-4 shadow-lg">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.08] pb-3">
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-sky-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      Evaluated Supplier Candidates ({currentDecision.supplier_options.length})
                    </h3>
                  </div>
                  <span className="text-[11px] text-[#EAF4F4]/60">
                    Click "View Evidence" on any supplier to inspect grounded SLA clauses
                  </span>
                </div>

                {/* Candidate Comparison Table */}
                <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
                  <table className="w-full text-left text-xs font-mono border-collapse">
                    <thead>
                      <tr className="bg-[#01353e]/80 border-b border-white/[0.08] text-[#EAF4F4]/70 uppercase text-[10px]">
                        <th className="py-2.5 px-3">Supplier</th>
                        <th className="py-2.5 px-3">Unit Cost</th>
                        <th className="py-2.5 px-3">Lead Time</th>
                        <th className="py-2.5 px-3">Delivery Slack</th>
                        <th className="py-2.5 px-3">MOQ</th>
                        <th className="py-2.5 px-3">Score Breakdown</th>
                        <th className="py-2.5 px-3">Total Score</th>
                        <th className="py-2.5 px-3 text-right">Feasibility</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.06]">
                      {currentDecision.supplier_options.map((s) => {
                        const isOptimal = currentDecision.selected_supplier?.supplier_id === s.supplier_id;
                        return (
                          <tr
                            key={s.supplier_id}
                            className={`hover:bg-white/[0.02] ${isOptimal ? 'bg-[#03D26F]/10 font-semibold' : ''}`}
                          >
                            <td className="py-2.5 px-3 font-sans">
                              <div className="font-bold text-white flex items-center gap-1.5">
                                <span>{s.supplier_name}</span>
                                {isOptimal && (
                                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40">
                                    OPTIMAL
                                  </span>
                                )}
                              </div>
                              <span className="text-[10px] text-[#EAF4F4]/50">{s.supplier_code}</span>
                            </td>
                            <td className="py-2.5 px-3 text-white">LKR {s.unit_cost.toLocaleString()}</td>
                            <td className="py-2.5 px-3 text-[#EAF4F4]/80">{s.lead_time_days}d</td>
                            <td className="py-2.5 px-3">{renderSlackBadge(s.delivery_slack_days)}</td>
                            <td className="py-2.5 px-3 text-[#EAF4F4]/80">{s.moq} u</td>
                            <td className="py-2.5 px-3 text-[10px] text-[#EAF4F4]/70">
                              {s.score_breakdown ? (
                                <div className="space-y-0.5">
                                  <div>C: {(s.score_breakdown.weighted_cost * 100).toFixed(1)} / {(s.score_breakdown.weight_cost * 100).toFixed(0)}</div>
                                  <div>D: {(s.score_breakdown.weighted_delivery * 100).toFixed(1)} / {(s.score_breakdown.weight_delivery * 100).toFixed(0)}</div>
                                  <div>S: {(s.score_breakdown.weighted_sla * 100).toFixed(1)} / {(s.score_breakdown.weight_sla * 100).toFixed(0)}</div>
                                  {s.score_breakdown.zero_slack_penalty_applied && (
                                    <div className="text-amber-300 text-[9px]">⚠️ Zero-Slack -0.10</div>
                                  )}
                                </div>
                              ) : (
                                <span>-</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3">
                              {s.score !== null && s.score !== undefined ? (
                                <span className="font-bold text-[#CEF431] text-sm">
                                  {(s.score * 100).toFixed(1)}
                                </span>
                              ) : (
                                <span className="text-[#EAF4F4]/40">-</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 text-right font-sans">
                              {s.signals?.is_restricted ? (
                                <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                  RESTRICTED
                                </span>
                              ) : !s.is_feasible ? (
                                <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30" title={s.disqualification_reason}>
                                  DISQUALIFIED
                                </span>
                              ) : (
                                <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                  FEASIBLE
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="space-y-3 pt-2">
                  {currentDecision.supplier_options.map((sup) => {
                    const isSelected =
                      currentDecision.selected_supplier?.supplier_id === sup.supplier_id;
                    const isExpanded = !!expandedSuppliers[sup.supplier_id];

                    return (
                      <div
                        key={sup.supplier_id}
                        className={`rounded-2xl border transition overflow-hidden ${
                          isSelected
                            ? 'bg-[#014651]/70 border-[#03D26F]/50 shadow-md'
                            : 'bg-[#01353e]/40 border-white/[0.06] hover:border-white/[0.12]'
                        }`}
                      >
                        {/* Supplier Card Header */}
                        <div className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-bold text-white text-sm">
                                {sup.supplier_name}
                              </span>
                              {sup.supplier_code && (
                                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.08] text-[#EAF4F4]/70">
                                  {sup.supplier_code}
                                </span>
                              )}
                              {isSelected && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 font-mono">
                                  Designated Optimal
                                </span>
                              )}
                              {sup.signals?.is_restricted || sup.policy_signals?.compliance_status === 'restricted' ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-mono">
                                  RESTRICTED
                                </span>
                              ) : !sup.is_feasible ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-mono">
                                  ❌ INFEASIBLE: {sup.disqualification_reason || 'Exceeds window'}
                                </span>
                              ) : sup.delivery_slack_days === 0 ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">
                                  ⚠️ FEASIBLE (CRITICAL ZERO-MARGIN)
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono">
                                  ✅ FEASIBLE
                                </span>
                              )}
                              {renderSlackBadge(sup.delivery_slack_days)}
                              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-[#CEF431]/20 text-[#CEF431] border border-[#CEF431]/30">
                                Total: {sup.weighted_score !== null && sup.weighted_score !== undefined ? `${sup.weighted_score.toFixed(1)}/100` : sup.score !== null && sup.score !== undefined ? `${(sup.score * 100).toFixed(1)}/100` : '-'}
                              </span>
                              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                SLA: {sup.sla_score !== null && sup.sla_score !== undefined ? `${sup.sla_score.toFixed(1)}/100` : sup.score_breakdown?.sla_score !== undefined ? `${sup.score_breakdown.sla_score.toFixed(1)}/100` : '80.0/100'}
                              </span>
                            </div>
                            <div className="text-[#EAF4F4]/70 text-[11px] mt-1.5 flex flex-wrap items-center gap-3 font-mono">
                              <span>
                                Unit Cost: <strong className="text-white">LKR {sup.unit_cost.toLocaleString()}</strong>
                              </span>
                              <span>•</span>
                              <span>MOQ: {sup.moq} units</span>
                              <span>•</span>
                              <span>Lead Time: <strong className="text-white">{sup.lead_time_days} days</strong></span>
                              <span>•</span>
                              <span>Required Window: <strong className="text-cyan-300">≤ {currentDecision.required_delivery_window_days || currentDecision.detected_condition?.required_delivery_window_days} days</strong></span>
                              {sup.estimated_cost !== null && sup.estimated_cost !== undefined && (
                                <>
                                  <span>•</span>
                                  <span>Total Est: LKR {sup.estimated_cost.toLocaleString()}</span>
                                </>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-2 self-end sm:self-center">
                            <button
                              onClick={() => toggleSupplierEvidence(sup.supplier_id)}
                              className="px-3 py-1.5 rounded-xl bg-[#01272e] hover:bg-[#01353e] border border-white/[0.1] text-xs font-semibold text-[#EAF4F4] transition flex items-center gap-1.5 cursor-pointer"
                            >
                              <span>{isExpanded ? 'Hide Evidence & Breakdown' : 'View Evidence & Breakdown'}</span>
                              {isExpanded ? (
                                <ChevronUp className="w-3.5 h-3.5 text-[#03D26F]" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5 text-[#03D26F]" />
                              )}
                            </button>
                          </div>
                        </div>

                        {/* Collapsible Accordion Body */}
                        {isExpanded && (
                          <div className="px-4 pb-4 pt-2 border-t border-white/[0.06] bg-[#01272e]/60 space-y-3 text-xs">
                            {/* Score Breakdown & Grounded SLA Factors */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                              {/* Score Breakdown */}
                              {sup.score_breakdown && (
                                <div className="p-3 rounded-xl bg-[#01353e]/40 border border-white/[0.08] space-y-2">
                                  <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-cyan-300 uppercase tracking-wider block font-mono">
                                      Situation-Aware Score Breakdown
                                    </span>
                                    <span className="text-xs font-bold font-mono text-[#CEF431]">
                                      {sup.score_breakdown.weighted_score ?? (sup.score_breakdown.total_score ? (sup.score_breakdown.total_score * 100).toFixed(1) : '-')} / 100
                                    </span>
                                  </div>
                                  <div className="space-y-1 font-mono text-[11px]">
                                    <div className="flex justify-between text-[#EAF4F4]/80">
                                      <span>Cost Score:</span>
                                      <span className="text-white">{sup.score_breakdown.cost_score ?? '-'} pts</span>
                                    </div>
                                    <div className="flex justify-between text-[#EAF4F4]/80">
                                      <span>Delivery Score:</span>
                                      <span className="text-white">{sup.score_breakdown.delivery_score ?? '-'} pts</span>
                                    </div>
                                    <div className="flex justify-between text-[#EAF4F4]/80">
                                      <span>Grounded SLA Score:</span>
                                      <span className="text-[#CEF431] font-bold">{sup.score_breakdown.sla_score ?? '-'} pts</span>
                                    </div>
                                    {sup.delivery_slack_days === 0 && (
                                      <div className="text-amber-300 text-[10px] pt-1 border-t border-white/[0.06]">
                                        ⚠️ Zero delivery slack penalty applied (critical execution margin).
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* Grounded SLA Factors */}
                              {(sup.policy_signals || sup.signals) && (
                                <div className="p-3 rounded-xl bg-[#01353e]/40 border border-purple-500/25 space-y-2">
                                  <span className="text-[10px] font-bold text-purple-300 uppercase tracking-wider block font-mono">
                                    Grounded SLA & Contract Factors
                                  </span>
                                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                                    <div>
                                      <span className="text-[#EAF4F4]/50 block text-[9px]">OTIF TARGET / BENCHMARK</span>
                                      <span className="text-white font-bold">
                                        {(sup.policy_signals?.otif_target || sup.signals?.contracted_otif_pct)
                                          ? `${sup.policy_signals?.otif_target || sup.signals?.contracted_otif_pct}%`
                                          : 'Standard'}
                                      </span>
                                    </div>
                                    <div>
                                      <span className="text-[#EAF4F4]/50 block text-[9px]">EMERGENCY SUITABILITY</span>
                                      <span className="text-white font-bold uppercase">
                                        {sup.policy_signals?.emergency_suitability || 'Standard'}
                                      </span>
                                    </div>
                                    <div>
                                      <span className="text-[#EAF4F4]/50 block text-[9px]">EXPEDITED SUPPORT</span>
                                      <span className="text-emerald-400 font-bold uppercase">
                                        {sup.policy_signals?.expedited_support || (sup.signals?.expedited_available ? 'Supported' : 'Standard')}
                                      </span>
                                    </div>
                                    <div>
                                      <span className="text-[#EAF4F4]/50 block text-[9px]">DELAY RISK / VARIANCE</span>
                                      <span className={sup.policy_signals?.delay_risk === 'high' ? 'text-rose-400 font-bold uppercase' : 'text-white uppercase'}>
                                        {sup.policy_signals?.delay_risk || 'Low'}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Advantages & Risks */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                              {/* Advantages */}
                              <div className="p-3 rounded-xl bg-[#01353e]/40 border border-[#03D26F]/15 space-y-1.5">
                                <span className="text-[10px] font-bold text-[#03D26F] uppercase tracking-wider block">
                                  Advantages
                                </span>
                                {sup.advantages && sup.advantages.length > 0 ? (
                                  <ul className="space-y-1 text-[11px] text-[#EAF4F4]/80">
                                    {sup.advantages.map((adv, aIdx) => (
                                      <li key={aIdx} className="flex items-start gap-1.5">
                                        <span className="text-[#03D26F]">•</span>
                                        <span>{adv}</span>
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <span className="text-[11px] text-[#EAF4F4]/50 italic">None specified</span>
                                )}
                              </div>

                              {/* Risks */}
                              <div className="p-3 rounded-xl bg-[#01353e]/40 border border-amber-500/15 space-y-1.5">
                                <span className="text-[10px] font-bold text-amber-300 uppercase tracking-wider block">
                                  Operational Risks
                                </span>
                                {sup.risks && sup.risks.length > 0 ? (
                                  <ul className="space-y-1 text-[11px] text-[#EAF4F4]/80">
                                    {sup.risks.map((risk, rIdx) => (
                                      <li key={rIdx} className="flex items-start gap-1.5">
                                        <span className="text-amber-400">•</span>
                                        <span>{risk}</span>
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <span className="text-[11px] text-[#EAF4F4]/50 italic">No operational risks flagged</span>
                                )}
                              </div>
                            </div>

                            {/* Document Evidence for this Candidate */}
                            <div className="space-y-2 pt-2">
                              <span className="text-[10px] font-bold text-emerald-300 uppercase tracking-wider flex items-center gap-1">
                                <FileText className="w-3 h-3 text-emerald-400" /> Grounded Document Evidence
                              </span>

                              {sup.evidence && sup.evidence.length > 0 ? (
                                <div className="space-y-2">
                                  {sup.evidence.map((ev, eIdx) => {
                                    const pageLabel = formatPageLabel(ev.page_number);
                                    const docType = formatDocumentType(ev.document_type);

                                    return (
                                      <div
                                        key={eIdx}
                                        className="p-3 rounded-xl bg-[#01353e]/50 border border-emerald-500/20 space-y-2 text-xs"
                                      >
                                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                                          <div className="flex items-center gap-1.5 min-w-0">
                                            <span className="font-bold text-white text-[11px] truncate">
                                              {ev.document_title || ev.title || 'Supplier Document'}
                                            </span>
                                            <span className="text-[10px] text-[#EAF4F4]/60 font-mono">
                                              • {docType}
                                            </span>
                                            {pageLabel && (
                                              <span className="text-[10px] font-mono text-[#CEF431] font-semibold">
                                                • {pageLabel}
                                              </span>
                                            )}
                                          </div>
                                          <div className="flex items-center gap-1">
                                            <span className="text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                              Document IR
                                            </span>
                                            <span className="text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                              Policy / SLA
                                            </span>
                                          </div>
                                        </div>

                                        <p className="text-[11px] text-[#EAF4F4]/90 italic bg-[#01272e]/80 p-2.5 rounded-lg border-l-2 border-emerald-400 leading-relaxed">
                                          "{ev.text}"
                                        </p>

                                        {typeof ev.distance === 'number' && (
                                          <div className="text-[9px] text-[#EAF4F4]/50 font-mono flex items-center justify-between">
                                            <span>Authority: {ev.authority || 'policy_or_sla'}</span>
                                            <span>Relevance Distance: {ev.distance.toFixed(4)} (Retrieval Relevance)</span>
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <p className="text-[11px] text-[#EAF4F4]/50 italic">
                                  No document evidence retrieved for this supplier candidate.
                                </p>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* SECTION 7: DETAILED AGENT TELEMETRY TABS */}
            <div className="px-6 sm:px-8 pt-2">
              <div className="border-b border-white/[0.08] flex items-center gap-2 text-xs">
                <button
                  onClick={() => setActiveTab('inventory')}
                  className={`pb-3 font-semibold border-b-2 transition cursor-pointer ${
                    activeTab === 'inventory'
                      ? 'border-cyan-400 text-cyan-300'
                      : 'border-transparent text-[#EAF4F4]/60 hover:text-white'
                  }`}
                >
                  Raw Inventory Telemetry
                </button>
                <button
                  onClick={() => setActiveTab('demand')}
                  className={`pb-3 font-semibold border-b-2 transition cursor-pointer ${
                    activeTab === 'demand'
                      ? 'border-[#CEF431] text-[#CEF431]'
                      : 'border-transparent text-[#EAF4F4]/60 hover:text-white'
                  }`}
                >
                  Raw Demand & Risk Forecast
                </button>
              </div>

              {/* Tab Contents */}
              <div className="py-4">
                {/* Tab 1: Inventory Agent Snapshot */}
                {activeTab === 'inventory' && (
                  <div className="p-5 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-4 text-xs">
                    <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
                      <span className="font-bold text-white text-sm">Inventory Agent (Member 1) Telemetry</span>
                      <span className="font-mono text-[#03D26F] uppercase font-bold">
                        Status: {currentDecision.inventory_context?.status || 'HEALTHY'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">On-Hand</div>
                        <div className="text-lg font-black text-white mt-1 font-mono">
                          {currentDecision.inventory_context?.on_hand ?? '-'}
                        </div>
                      </div>
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Reserved</div>
                        <div className="text-lg font-black text-cyan-300 mt-1 font-mono">
                          {currentDecision.inventory_context?.reserved ?? '-'}
                        </div>
                      </div>
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Incoming Pipeline</div>
                        <div className="text-lg font-black text-[#CEF431] mt-1 font-mono">
                          {currentDecision.inventory_context?.incoming ?? '-'}
                        </div>
                      </div>
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Reorder Point (ROP)</div>
                        <div className="text-lg font-black text-[#03D26F] mt-1 font-mono">
                          {currentDecision.inventory_context?.reorder_point ?? '-'}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab 2: Demand Agent Snapshot */}
                {activeTab === 'demand' && (
                  <div className="p-5 rounded-2xl bg-[#01272e]/80 border border-white/[0.08] space-y-4 text-xs">
                    <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
                      <span className="font-bold text-white text-sm">Demand & Risk Agent (Member 2) Forecast</span>
                      <span className="font-mono text-cyan-300 uppercase font-bold">
                        Model: {currentDecision.demand_context?.selected_model || 'SMA Forecast'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Forecast Horizon</div>
                        <div className="text-lg font-black text-white mt-1 font-mono">
                          {currentDecision.demand_context?.forecast_horizon_days ?? 14} days
                        </div>
                      </div>
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Total Demand</div>
                        <div className="text-lg font-black text-[#03D26F] mt-1 font-mono">
                          {currentDecision.demand_context?.total_forecasted_demand ?? 0} units
                        </div>
                      </div>
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Lead-Time Demand</div>
                        <div className="text-lg font-black text-cyan-300 mt-1 font-mono">
                          {currentDecision.demand_context?.expected_demand_over_lead_time ?? 0} units
                        </div>
                      </div>
                      <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                        <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Projected Stockout</div>
                        <div className="text-lg font-black text-[#CEF431] mt-1 font-mono truncate">
                          {currentDecision.demand_context?.projected_stockout_date || 'None in period'}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* Historical Decisions Table */}
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-[#EAF4F4]">
                Decision & Requisition Audit Trail
              </h2>
              <p className="text-xs text-[#EAF4F4]/60">
                Immutable ledger of agent recommendations, human approvals, and rejection rationales.
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
                No decision history records found.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/[0.08] bg-[#01272e]/80 text-[#EAF4F4]/70 uppercase tracking-wider font-semibold text-[10px]">
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
                        <td className="py-3 px-4 font-bold">
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
                            onClick={() => setCurrentDecision(item)}
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

