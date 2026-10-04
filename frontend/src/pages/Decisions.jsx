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

          <form onSubmit={handleGenerateDecision} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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

            {/* Procurement Urgency */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#EAF4F4]/80">Procurement Urgency</label>
              <select
                value={urgency}
                onChange={(e) => setUrgency(e.target.value)}
                className="w-full bg-[#01272e]/90 border border-white/[0.1] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/30"
              >
                <option value="normal" className="bg-[#01272e] text-white">Normal (Cost Optimized)</option>
                <option value="high" className="bg-[#01272e] text-white">High (Balanced SLA)</option>
                <option value="emergency" className="bg-[#01272e] text-white">Emergency (Expedited)</option>
              </select>
            </div>

            {/* Run Action Bar */}
            <div className="sm:col-span-2 lg:col-span-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2">
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

            {/* Warnings alert if any */}
            {currentDecision.warnings && currentDecision.warnings.length > 0 && (
              <div className="mx-6 sm:mx-8 p-4 rounded-2xl bg-amber-500/15 border border-amber-500/25 space-y-1.5">
                <div className="flex items-center gap-1.5 text-amber-300 text-xs font-bold">
                  <AlertTriangle className="w-4 h-4" /> Operational Safeguards & Missing Data Notices:
                </div>
                <ul className="text-xs text-amber-200/90 list-disc list-inside space-y-0.5 pl-1">
                  {currentDecision.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Context Navigation Tabs */}
            <div className="px-6 sm:px-8 border-b border-white/[0.08] flex flex-wrap items-center gap-2 text-xs">
              <button
                onClick={() => setActiveTab('reasoning')}
                className={`pb-3 font-semibold border-b-2 transition cursor-pointer ${
                  activeTab === 'reasoning'
                    ? 'border-[#03D26F] text-[#03D26F]'
                    : 'border-transparent text-[#EAF4F4]/60 hover:text-white'
                }`}
              >
                Grok AI Explainability & Synthesis
              </button>
              <button
                onClick={() => setActiveTab('inventory')}
                className={`pb-3 font-semibold border-b-2 transition cursor-pointer ${
                  activeTab === 'inventory'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-[#EAF4F4]/60 hover:text-white'
                }`}
              >
                Inventory Agent Data
              </button>
              <button
                onClick={() => setActiveTab('demand')}
                className={`pb-3 font-semibold border-b-2 transition cursor-pointer ${
                  activeTab === 'demand'
                    ? 'border-[#CEF431] text-[#CEF431]'
                    : 'border-transparent text-[#EAF4F4]/60 hover:text-white'
                }`}
              >
                Demand & Risk Data
              </button>
              <button
                onClick={() => setActiveTab('suppliers')}
                className={`pb-3 font-semibold border-b-2 transition cursor-pointer ${
                  activeTab === 'suppliers'
                    ? 'border-emerald-400 text-emerald-300'
                    : 'border-transparent text-[#EAF4F4]/60 hover:text-white'
                }`}
              >
                Supplier Options Evaluated ({currentDecision.supplier_options?.length || 0})
              </button>
            </div>

            {/* Tab Contents */}
            <div className="px-6 sm:px-8 pb-8">
              {/* Tab 1: Grok Reasoning */}
              {activeTab === 'reasoning' && (
                <div className="space-y-4">
                  <div className="p-5 rounded-2xl bg-[#01272e]/90 border border-[#03D26F]/25 space-y-3 shadow-inner">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-[#03D26F] flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4" /> Grok LLM Explainable Rationale
                      </span>
                      {currentDecision.confidence !== null && (
                        <span className="text-[#CEF431] font-mono text-[11px] font-bold bg-[#CEF431]/10 px-2.5 py-0.5 rounded-full border border-[#CEF431]/20">
                          Confidence: {(currentDecision.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#EAF4F4] leading-relaxed whitespace-pre-line font-normal">
                      {currentDecision.reasoning}
                    </p>
                  </div>

                  {/* Key Factors */}
                  {currentDecision.factors && currentDecision.factors.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-xs font-bold text-[#EAF4F4]/70 uppercase tracking-wider">
                        Key Strategic Factors Considered
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                        {currentDecision.factors.map((factor, idx) => (
                          <div
                            key={idx}
                            className="p-3 rounded-xl bg-[#01272e]/70 border border-white/[0.06] text-[#EAF4F4] flex items-start gap-2.5"
                          >
                            <CheckCircle2 className="w-4 h-4 text-[#03D26F] shrink-0 mt-0.5" />
                            <span>{factor}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Policy References */}
                  {currentDecision.policy_references && currentDecision.policy_references.length > 0 && (
                    <div className="space-y-2 pt-2">
                      <h3 className="text-[11px] font-bold text-[#EAF4F4]/60 uppercase tracking-wider">
                        Corporate Policies Referenced
                      </h3>
                      <div className="text-xs text-[#EAF4F4]/80 space-y-1.5">
                        {currentDecision.policy_references.map((p, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <ShieldCheck className="w-3.5 h-3.5 text-[#CEF431]" />
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
                      <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Available Stock</div>
                      <div className="text-lg font-black text-[#03D26F] mt-1 font-mono">
                        {currentDecision.inventory_context?.available_stock ?? '-'}
                      </div>
                    </div>
                    <div className="p-3.5 bg-[#01353e]/60 rounded-xl border border-white/[0.06]">
                      <div className="text-[#EAF4F4]/60 text-[10px] font-semibold uppercase">Reorder Point (ROP)</div>
                      <div className="text-lg font-black text-[#CEF431] mt-1 font-mono">
                        {currentDecision.inventory_context?.reorder_point ?? '-'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 3: Demand Agent Snapshot */}
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

              {/* Tab 4: Supplier Intelligence Snapshot */}
              {activeTab === 'suppliers' && (
                <div className="space-y-3">
                  <div className="text-xs text-[#EAF4F4]/70">
                    Evaluated vendor proposals provided by Supplier Intelligence Agent (Member 3):
                  </div>
                  <div className="space-y-2.5">
                    {currentDecision.supplier_options?.map((sup) => {
                      const isSelected =
                        currentDecision.selected_supplier?.supplier_id === sup.supplier_id;
                      return (
                        <div
                          key={sup.supplier_id}
                          className={`p-4 rounded-2xl border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                            isSelected
                              ? 'bg-[#014651]/80 border-[#03D26F]/50 shadow-md'
                              : 'bg-[#01272e]/70 border-white/[0.06]'
                          }`}
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-white text-sm">
                                {sup.supplier_name}
                              </span>
                              {isSelected && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 font-mono">
                                  Designated Optimal
                                </span>
                              )}
                            </div>
                            <div className="text-[#EAF4F4]/70 text-[11px] mt-1 flex flex-wrap gap-3 font-mono">
                              <span>Unit Cost: LKR {sup.unit_cost.toLocaleString()}</span>
                              <span>•</span>
                              <span>MOQ: {sup.moq} units</span>
                              <span>•</span>
                              <span>Lead Time: {sup.lead_time_days} days</span>
                            </div>
                          </div>

                          <div className="text-right text-[11px]">
                            {sup.advantages && sup.advantages.length > 0 && (
                              <span className="text-[#03D26F] font-semibold block">{sup.advantages[0]}</span>
                            )}
                            {sup.risks && sup.risks.length > 0 && (
                              <span className="text-amber-300 block">{sup.risks[0]}</span>
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

