import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Navbar from '../components/Navbar';
import {
  Bot,
  User as UserIcon,
  Send,
  Plus,
  Trash2,
  Sparkles,
  AlertTriangle,
  HelpCircle,
  FileText,
  Database,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  ArrowRight,
  Package,
  TrendingUp,
  ShieldAlert,
  Truck,
  CheckCircle2,
  Info,
  Scale,
  X,
} from 'lucide-react';
import {
  listConversations,
  getConversation,
  createConversation,
  deleteConversation,
  sendMessage,
} from '../services/chatApi';

const STARTER_PROMPTS = [
  'Should we replenish Wireless Mouse?',
  'What is the stockout risk for Wireless Mouse?',
  'Compare suppliers for DEMO-001.',
  'What does our emergency procurement policy say?',
  "What is TechSource's delivery SLA?",
  'How many Wireless Mice are available?',
];

// Helper to strip markdown symbols from sidebar previews
const stripMarkdownPreview = (text) => {
  if (!text) return '';
  return text
    .replace(/[#*`_~>[\]()\-!]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
};

// Helper to format conversation timestamps
const formatConvTime = (dateStr) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch (e) {
    return '';
  }
};

export default function Assistant() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [error, setError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [expandedSources, setExpandedSources] = useState({});
  const [expandedSections, setExpandedSections] = useState({});
  const [customHorizonMsgId, setCustomHorizonMsgId] = useState(null);
  const [customHorizonInput, setCustomHorizonInput] = useState('');

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    fetchConversations();
  }, []);

  const fetchConversations = async () => {
    setLoadingConversations(true);
    const res = await listConversations();
    if (res.success) {
      setConversations(res.data);
      if (res.data.length > 0 && !activeConversationId) {
        selectConversation(res.data[0].id);
      }
    } else {
      setError(res.error);
    }
    setLoadingConversations(false);
  };

  const selectConversation = async (convId) => {
    setActiveConversationId(convId);
    setSidebarOpen(false);
    setError(null);
    setLoading(true);
    const res = await getConversation(convId);
    if (res.success) {
      setMessages(res.data.messages || []);
    } else {
      setError(res.error);
    }
    setLoading(false);
  };

  const handleNewChat = async (starterPrompt = null) => {
    setError(null);
    const res = await createConversation();
    if (res.success) {
      setConversations((prev) => [res.data, ...prev]);
      setActiveConversationId(res.data.id);
      setMessages([]);
      if (starterPrompt) {
        handleSend(starterPrompt, res.data.id);
      }
    } else {
      setError(res.error);
    }
  };

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this conversation?')) return;

    const res = await deleteConversation(convId);
    if (res.success) {
      const remaining = conversations.filter((c) => c.id !== convId);
      setConversations(remaining);
      if (activeConversationId === convId) {
        if (remaining.length > 0) {
          selectConversation(remaining[0].id);
        } else {
          setActiveConversationId(null);
          setMessages([]);
        }
      }
    } else {
      setError(res.error);
    }
  };

  const handleSend = async (textToSend = null, explicitConvId = null) => {
    const text = (textToSend || inputText).trim();
    if (!text || loading) return;

    let targetConvId = explicitConvId || activeConversationId;

    if (!targetConvId) {
      const createRes = await createConversation();
      if (!createRes.success) {
        setError(createRes.error);
        return;
      }
      targetConvId = createRes.data.id;
      setConversations((prev) => [createRes.data, ...prev]);
      setActiveConversationId(targetConvId);
    }

    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      conversation_id: targetConvId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMessage]);
    setInputText('');
    setCustomHorizonMsgId(null);
    setCustomHorizonInput('');
    setLoading(true);
    setError(null);

    const res = await sendMessage(targetConvId, text);
    if (res.success) {
      const assistantMessage = {
        id: res.data.message_id,
        conversation_id: targetConvId,
        role: 'assistant',
        content: res.data.answer,
        message_metadata: {
          intent: res.data.intent,
          status: res.data.status,
          sources: res.data.sources,
          needs_clarification: res.data.needs_clarification,
          clarification_prompt: res.data.clarification_prompt,
          clarification_options: res.data.clarification_options,
          decision_summary: res.data.decision_summary,
          decision_details: res.data.decision_details,
          inventory_snapshot: res.data.inventory_snapshot,
          forecast_summary: res.data.forecast_summary,
          stockout_summary: res.data.stockout_summary,
          supplier_offer: res.data.supplier_offer,
          forecast_horizon_days: res.data.forecast_horizon_days,
          agent_outputs_used: res.data.agent_outputs_used,
        },
        created_at: res.data.created_at,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      listConversations().then((cRes) => {
        if (cRes.success) setConversations(cRes.data);
      });
    } else {
      setError(res.error);
    }
    setLoading(false);
  };

  const handleCustomHorizonSubmit = () => {
    const val = parseInt(customHorizonInput.trim(), 10);
    if (isNaN(val) || val < 1 || val > 90) {
      setError('Please choose a forecast horizon between 1 and 90 days.');
      return;
    }
    setError(null);
    handleSend(`${val} days`);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleSources = (msgId) => {
    setExpandedSources((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const toggleSection = (sectionKey) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionKey]: !prev[sectionKey],
    }));
  };

  // Helper to extract 3-5 bullets under Chat Replenishment Recommendation
  const extractChatDecisionBullets = (decision, details) => {
    const bullets = [];
    if (details?.factors && details.factors.length > 0) {
      return details.factors.slice(0, 5);
    }

    if (details?.inventory_demand) {
      const inv = details.inventory_demand;
      if (inv.days_until_buffer_breach === 0) {
        bullets.push('The ROP safety buffer is already breached under current available inventory.');
      } else if (inv.days_until_buffer_breach != null) {
        bullets.push(`ROP buffer is projected to breach in ~${inv.days_until_buffer_breach} days.`);
      }
      if (inv.days_until_stockout != null) {
        bullets.push(`Available inventory may be exhausted in approximately ${inv.days_until_stockout} days.`);
      }
    }

    if (decision?.selected_supplier_name) {
      bullets.push(
        `${decision.selected_supplier_name} meets the delivery deadline of ≤ ${decision.required_delivery_window_days} days.`
      );
    }

    if (bullets.length < 3) {
      bullets.push('Grounded under active commercial terms and corporate procurement threshold policies.');
    }

    return bullets.slice(0, 5);
  };

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col font-sans">
      <Navbar />

      <div className="flex-1 flex overflow-hidden relative max-w-7xl w-full mx-auto p-2 sm:p-4 gap-4">
        {/* Mobile Sidebar Toggle Button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="lg:hidden fixed bottom-20 right-4 z-40 bg-[#03D26F] text-[#161514] p-3 rounded-full shadow-lg hover:bg-[#02be63] transition-all cursor-pointer"
          title="Toggle Conversations"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Layers className="w-5 h-5" />}
        </button>

        {/* 6. CONVERSATION SIDEBAR */}
        <aside
          className={`fixed lg:static inset-y-0 left-0 z-30 w-72 sm:w-80 bg-[#01353e]/95 lg:bg-[#01353e]/70 backdrop-blur-xl border border-white/[0.08] rounded-2xl flex flex-col transition-transform duration-300 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          }`}
        >
          {/* Sidebar Header */}
          <div className="p-3.5 border-b border-white/[0.08] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-[#03D26F]" />
              <h2 className="font-bold text-xs uppercase tracking-wider text-white">Conversations</h2>
            </div>
            <button
              onClick={() => handleNewChat()}
              className="inline-flex items-center gap-1.5 text-xs bg-[#03D26F]/20 hover:bg-[#03D26F]/30 text-[#03D26F] border border-[#03D26F]/40 px-2.5 py-1.5 rounded-xl transition-all font-semibold cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Chat</span>
            </button>
          </div>

          {/* Conversations Scroll Area */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {loadingConversations ? (
              <div className="p-4 text-center text-xs text-[#EAF4F4]/50 animate-pulse">
                Loading history...
              </div>
            ) : conversations.length === 0 ? (
              <div className="p-6 text-center text-xs text-[#EAF4F4]/50">
                No conversations yet. Start a new chat!
              </div>
            ) : (
              conversations.map((conv) => {
                const isActive = conv.id === activeConversationId;
                const cleanPreview = stripMarkdownPreview(conv.last_message);
                const timeLabel = formatConvTime(conv.updated_at || conv.created_at);

                return (
                  <div
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    className={`group relative flex items-start justify-between p-3 rounded-xl cursor-pointer text-xs transition-all ${
                      isActive
                        ? 'bg-[#03D26F]/20 border border-[#03D26F]/40 text-white font-medium shadow-sm'
                        : 'hover:bg-white/[0.04] text-[#EAF4F4]/80 border border-transparent'
                    }`}
                  >
                    <div className="flex-1 min-w-0 pr-2">
                      <div className="flex items-center justify-between gap-1">
                        <span className="truncate font-semibold text-white text-xs">
                          {conv.title || 'Conversation'}
                        </span>
                        {timeLabel && (
                          <span className="text-[10px] text-[#EAF4F4]/40 font-mono shrink-0">
                            {timeLabel}
                          </span>
                        )}
                      </div>
                      {cleanPreview && (
                        <p className="text-[11px] text-[#EAF4F4]/60 truncate mt-0.5 leading-snug">
                          {cleanPreview}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      className="opacity-0 group-hover:opacity-100 hover:text-rose-400 p-1 rounded transition-opacity cursor-pointer shrink-0"
                      title="Delete Conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* MAIN CHAT INTERFACE */}
        <main className="flex-1 flex flex-col bg-[#01353e]/40 backdrop-blur-xl border border-white/[0.08] rounded-2xl overflow-hidden shadow-2xl relative">
          {/* 7. SIMPLIFIED AI ASSISTANT HEADER */}
          <div className="px-5 py-3 border-b border-white/[0.08] flex items-center justify-between bg-[#01272e]/90">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-[#03D26F]/20 border border-[#03D26F]/40 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-[#03D26F]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-bold text-white tracking-wide">
                    SmartSupply AI Assistant
                  </h1>
                  <span className="text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-[#03D26F]/15 text-[#03D26F] border border-[#03D26F]/30">
                    Live Agents Active
                  </span>
                </div>
                <p className="text-[11px] text-[#EAF4F4]/65">
                  Ask about inventory, demand, suppliers and procurement.
                </p>
              </div>
            </div>
          </div>

          {/* 8. MESSAGES CONTAINER WITH CONTROLLED WIDTHS */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
            {messages.length === 0 && !loading ? (
              // Empty State
              <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto my-auto p-6">
                <div className="w-12 h-12 rounded-2xl bg-[#03D26F]/15 border border-[#03D26F]/30 flex items-center justify-center mb-3 shadow-lg shadow-[#03D26F]/5">
                  <Sparkles className="w-6 h-6 text-[#03D26F]" />
                </div>
                <h3 className="text-base font-bold text-white mb-1">
                  How can I assist your supply chain today?
                </h3>
                <p className="text-xs text-[#EAF4F4]/70 mb-5 leading-relaxed">
                  Query real-time inventory positions, demand volatility forecasts, supplier terms,
                  and replenishment requisitions.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full text-left">
                  {STARTER_PROMPTS.map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(prompt)}
                      className="p-2.5 bg-[#01272e]/80 hover:bg-[#01353e] border border-white/[0.08] hover:border-[#03D26F]/40 rounded-xl text-xs text-[#EAF4F4]/90 transition-all flex items-center justify-between group cursor-pointer"
                    >
                      <span className="truncate pr-2">{prompt}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-[#03D26F] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => {
                const isUser = msg.role === 'user';
                const meta = msg.message_metadata || msg.metadata || {};
                const isDegraded = meta.status === 'degraded';
                const isClarification = meta.status === 'clarification_needed' || meta.needs_clarification;
                const decision = meta.decision_summary;
                const decisionDetails = meta.decision_details;
                const invSnapshot = meta.inventory_snapshot;
                const forecastSummary = meta.forecast_summary;
                const stockoutSummary = meta.stockout_summary;
                const supplierOffer = meta.supplier_offer;
                const clarificationOptions = meta.clarification_options || [];
                const sources = meta.sources || [];
                const hasSources = sources.length > 0;
                const isExpandedSources = expandedSources[msg.id];

                return (
                  <div
                    key={msg.id}
                    className={`flex gap-2.5 w-full ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    {/* Assistant Avatar */}
                    {!isUser && (
                      <div className="w-7 h-7 rounded-lg bg-[#03D26F]/20 border border-[#03D26F]/40 text-[#03D26F] flex items-center justify-center shrink-0 text-xs mt-0.5">
                        <Bot className="w-3.5 h-3.5" />
                      </div>
                    )}

                    {/* Content Box with Strict Max Width */}
                    <div
                      className={`space-y-2.5 ${
                        isUser
                          ? 'max-w-xl'
                          : decision
                          ? 'max-w-3xl w-full'
                          : 'max-w-2xl w-full'
                      }`}
                    >
                      {/* 9. COMPACT STATUS BANNER */}
                      {!isUser && isDegraded && (
                        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] font-medium">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          <span>⚠️ AI wording unavailable — showing verified SmartSupply results.</span>
                        </div>
                      )}

                      {!isUser && isClarification && (
                        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-200 text-[11px] font-medium">
                          <HelpCircle className="w-3.5 h-3.5 text-[#03D26F] shrink-0" />
                          <span>Parameter clarification requested to ensure accurate analysis.</span>
                        </div>
                      )}

                      {/* 10. REPLENISHMENT RECOMMENDATION CARD WITH 3-5 BULLETS & ACCORDIONS */}
                      {!isUser && decision && (
                        <div className="p-4 sm:p-5 rounded-2xl bg-[#01272e] border border-[#03D26F]/40 shadow-lg space-y-3.5">
                          {/* Card Header */}
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.08] pb-2.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-[#03D26F] flex items-center gap-1.5">
                              <Package className="w-3.5 h-3.5" />
                              Replenishment Recommendation
                            </span>
                            <span
                              className={`text-[10px] font-bold font-mono uppercase px-2 py-0.5 rounded-full ${
                                decision.urgency === 'EMERGENCY'
                                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                  : decision.urgency === 'HIGH'
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                  : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              }`}
                            >
                              {decision.urgency} Urgency
                            </span>
                          </div>

                          {/* Primary Stats Grid */}
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                            <div className="p-2.5 rounded-xl bg-[#01353e]/60 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block uppercase font-mono">Product</span>
                              <span className="font-semibold text-white truncate block mt-0.5">{decision.product_name}</span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#01353e]/60 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block uppercase font-mono">Recommended Order</span>
                              <span className="font-bold text-[#03D26F] text-sm block mt-0.5">
                                {decision.recommended_order_quantity} units
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#01353e]/60 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block uppercase font-mono">Required Delivery</span>
                              <span className="font-semibold text-cyan-200 block mt-0.5">
                                ≤ {decision.required_delivery_window_days} days
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#01353e]/60 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block uppercase font-mono">Supplier</span>
                              <span className="font-semibold text-white truncate block mt-0.5">
                                {decision.selected_supplier_name || 'N/A'}
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#01353e]/60 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block uppercase font-mono">Lead / Slack</span>
                              <span className="font-semibold text-white block mt-0.5">
                                {decision.lead_time_days ?? '—'}d (Slack: {decision.delivery_slack_days ?? 0}d)
                              </span>
                            </div>
                            <div className="p-2.5 rounded-xl bg-[#01353e]/60 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block uppercase font-mono">Estimated Spend</span>
                              <span className="font-bold text-[#CEF431] block mt-0.5">
                                {decision.estimated_total_cost ? `LKR ${decision.estimated_total_cost.toLocaleString()}` : 'N/A'}
                              </span>
                            </div>
                          </div>

                          {/* WHY THIS RECOMMENDATION? (3-5 bullets only) */}
                          <div className="p-3.5 rounded-xl bg-[#01353e]/40 border border-white/[0.06] space-y-2">
                            <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                              <CheckCircle2 className="w-3.5 h-3.5 text-[#03D26F]" />
                              Why this recommendation?
                            </span>
                            <ul className="space-y-1 text-xs text-[#EAF4F4]/90">
                              {extractChatDecisionBullets(decision, decisionDetails).map((bullet, bIdx) => (
                                <li key={bIdx} className="flex items-start gap-2 leading-relaxed">
                                  <span className="text-[#03D26F] font-bold">•</span>
                                  <span>{bullet}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          {/* ACCORDIONS: INVENTORY & DEMAND, SUPPLIER COMPARISON, POLICY & EVIDENCE, ASSUMPTIONS */}
                          <div className="space-y-1.5 pt-1">
                            {/* Accordion 1: Inventory & Demand */}
                            {decisionDetails?.inventory_demand && (
                              <div className="border border-white/[0.08] rounded-xl overflow-hidden bg-black/20">
                                <button
                                  type="button"
                                  onClick={() => toggleSection(`${msg.id}-inv_demand`)}
                                  className="w-full px-3 py-2 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition-colors cursor-pointer"
                                >
                                  <span className="flex items-center gap-2">
                                    <Package className="w-3.5 h-3.5 text-[#03D26F]" />
                                    <span>Inventory & Demand</span>
                                  </span>
                                  {expandedSections[`${msg.id}-inv_demand`] ? (
                                    <ChevronUp className="w-3.5 h-3.5 text-[#03D26F]" />
                                  ) : (
                                    <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                  )}
                                </button>
                                {expandedSections[`${msg.id}-inv_demand`] && (
                                  <div className="p-3 text-xs space-y-2 border-t border-white/[0.06] bg-black/30">
                                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                      <div className="p-2 rounded bg-white/[0.03]">
                                        <span className="text-[#EAF4F4]/50 text-[10px] block">Forecast Demand</span>
                                        <span className="font-semibold text-white">
                                          {decisionDetails.inventory_demand.total_forecasted_demand} units ({decisionDetails.inventory_demand.selected_model})
                                        </span>
                                      </div>
                                      <div className="p-2 rounded bg-white/[0.03]">
                                        <span className="text-[#EAF4F4]/50 text-[10px] block">Lead Demand</span>
                                        <span className="font-semibold text-white">
                                          {decisionDetails.inventory_demand.expected_demand_over_lead_time} units
                                        </span>
                                      </div>
                                      <div className="p-2 rounded bg-white/[0.03]">
                                        <span className="text-[#EAF4F4]/50 text-[10px] block">Effective Stock</span>
                                        <span className="font-semibold text-white">
                                          {decisionDetails.inventory_demand.effective_inventory} units
                                        </span>
                                      </div>
                                      <div className="p-2 rounded bg-white/[0.03]">
                                        <span className="text-[#EAF4F4]/50 text-[10px] block">Stockout Timing</span>
                                        <span className="font-semibold text-rose-300">
                                          {decisionDetails.inventory_demand.days_until_stockout != null
                                            ? `~${decisionDetails.inventory_demand.days_until_stockout} days`
                                            : 'Safe'}
                                        </span>
                                      </div>
                                      <div className="p-2 rounded bg-white/[0.03]">
                                        <span className="text-[#EAF4F4]/50 text-[10px] block">Buffer Breach</span>
                                        <span className="font-semibold text-amber-300">
                                          {decisionDetails.inventory_demand.days_until_buffer_breach === 0
                                            ? 'BREACHED NOW'
                                            : decisionDetails.inventory_demand.days_until_buffer_breach != null
                                            ? `~${decisionDetails.inventory_demand.days_until_buffer_breach} days`
                                            : 'Safe'}
                                        </span>
                                      </div>
                                      <div className="p-2 rounded bg-white/[0.03]">
                                        <span className="text-[#EAF4F4]/50 text-[10px] block">ROP Buffer</span>
                                        <span className="font-semibold text-white">
                                          {decisionDetails.inventory_demand.reorder_point} units
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Accordion 2: Supplier Comparison */}
                            {decisionDetails?.supplier_comparison && decisionDetails.supplier_comparison.length > 0 && (
                              <div className="border border-white/[0.08] rounded-xl overflow-hidden bg-black/20">
                                <button
                                  type="button"
                                  onClick={() => toggleSection(`${msg.id}-sup_compare`)}
                                  className="w-full px-3 py-2 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition-colors cursor-pointer"
                                >
                                  <span className="flex items-center gap-2">
                                    <Truck className="w-3.5 h-3.5 text-cyan-300" />
                                    <span>Supplier Comparison ({decisionDetails.supplier_comparison.length})</span>
                                  </span>
                                  {expandedSections[`${msg.id}-sup_compare`] ? (
                                    <ChevronUp className="w-3.5 h-3.5 text-[#03D26F]" />
                                  ) : (
                                    <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                  )}
                                </button>
                                {expandedSections[`${msg.id}-sup_compare`] && (
                                  <div className="p-2.5 text-xs border-t border-white/[0.06] bg-black/30 overflow-x-auto">
                                    <table className="w-full text-left border-collapse text-[10px] font-mono">
                                      <thead>
                                        <tr className="border-b border-white/10 text-[#EAF4F4]/60 uppercase">
                                          <th className="py-1.5 px-2">Supplier</th>
                                          <th className="py-1.5 px-2">Cost</th>
                                          <th className="py-1.5 px-2">MOQ</th>
                                          <th className="py-1.5 px-2">Lead</th>
                                          <th className="py-1.5 px-2">Slack</th>
                                          <th className="py-1.5 px-2">Score</th>
                                          <th className="py-1.5 px-2">Status</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-white/[0.04]">
                                        {decisionDetails.supplier_comparison.map((sup, idx) => (
                                          <tr key={idx} className={sup.selected ? 'bg-[#03D26F]/10 text-white font-semibold' : 'text-[#EAF4F4]/80'}>
                                            <td className="py-1.5 px-2 font-sans truncate max-w-[120px]">
                                              {sup.supplier_name} {sup.selected ? '✓' : ''}
                                            </td>
                                            <td className="py-1.5 px-2">{sup.unit_cost != null ? `LKR ${Number(sup.unit_cost).toLocaleString()}` : '—'}</td>
                                            <td className="py-1.5 px-2">{sup.moq ?? '—'}</td>
                                            <td className="py-1.5 px-2">{sup.lead_time_days ?? '—'}d</td>
                                            <td className="py-1.5 px-2">{sup.delivery_slack_days ?? '—'}d</td>
                                            <td className="py-1.5 px-2">{sup.weighted_score != null ? Number(sup.weighted_score).toFixed(1) : '—'}</td>
                                            <td className="py-1.5 px-2">
                                              {sup.selected ? (
                                                <span className="text-[#03D26F] text-[9px] uppercase font-bold">Selected</span>
                                              ) : sup.is_feasible ? (
                                                <span className="text-cyan-300 text-[9px]">Eligible</span>
                                              ) : (
                                                <span className="text-rose-400 text-[9px]">Disqualified</span>
                                              )}
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Accordion 3: Policy & Evidence */}
                            {hasSources && (
                              <div className="border border-white/[0.08] rounded-xl overflow-hidden bg-black/20">
                                <button
                                  type="button"
                                  onClick={() => toggleSection(`${msg.id}-policy_evidence`)}
                                  className="w-full px-3 py-2 text-left flex items-center justify-between text-xs font-semibold text-[#EAF4F4] hover:bg-white/[0.03] transition-colors cursor-pointer"
                                >
                                  <span className="flex items-center gap-2">
                                    <Scale className="w-3.5 h-3.5 text-purple-300" />
                                    <span>Policy & Evidence ({sources.length})</span>
                                  </span>
                                  {expandedSections[`${msg.id}-policy_evidence`] ? (
                                    <ChevronUp className="w-3.5 h-3.5 text-[#03D26F]" />
                                  ) : (
                                    <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                  )}
                                </button>
                                {expandedSections[`${msg.id}-policy_evidence`] && (
                                  <div className="p-3 text-xs space-y-2 border-t border-white/[0.06] bg-black/30">
                                    {sources.map((s, idx) => (
                                      <div key={idx} className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.05] space-y-1">
                                        <div className="flex items-center justify-between text-xs font-semibold text-white">
                                          <span>{s.document_title || s.label || 'Authoritative Source'}</span>
                                          <span className="text-[10px] font-mono text-[#CEF431]">
                                            {s.page_number ? `Page ${s.page_number}` : ''}
                                          </span>
                                        </div>
                                        {s.excerpt && (
                                          <p className="text-[11px] text-[#EAF4F4]/80 italic border-l-2 border-[#03D26F]/60 pl-2 mt-1">
                                            "{s.excerpt}"
                                          </p>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Accordion 4: Assumptions */}
                            {decisionDetails?.warnings && decisionDetails.warnings.length > 0 && (
                              <div className="border border-white/[0.08] rounded-xl overflow-hidden bg-black/20">
                                <button
                                  type="button"
                                  onClick={() => toggleSection(`${msg.id}-assumptions`)}
                                  className="w-full px-3 py-2 text-left flex items-center justify-between text-xs font-semibold text-amber-300 hover:bg-white/[0.03] transition-colors cursor-pointer"
                                >
                                  <span className="flex items-center gap-2">
                                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                                    <span>Assumptions ({decisionDetails.warnings.length})</span>
                                  </span>
                                  {expandedSections[`${msg.id}-assumptions`] ? (
                                    <ChevronUp className="w-3.5 h-3.5 text-amber-400" />
                                  ) : (
                                    <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                  )}
                                </button>
                                {expandedSections[`${msg.id}-assumptions`] && (
                                  <div className="p-3 text-xs space-y-1.5 border-t border-white/[0.06] bg-black/30 text-amber-200/90">
                                    <ul className="list-disc pl-4 space-y-1">
                                      {decisionDetails.warnings.map((w, i) => (
                                        <li key={i}>{w}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Compact Standalone Cards (Inventory, Demand, Stockout, Supplier Offer) when not a full decision */}
                      {!isUser && !decision && invSnapshot && (
                        <div className="p-3.5 rounded-xl bg-[#01272e] border border-[#03D26F]/30 shadow-md space-y-2">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-[#03D26F] flex items-center gap-1.5">
                              <Package className="w-3.5 h-3.5" />
                              Inventory Snapshot • {invSnapshot.product_name}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Available</span>
                              <span className="text-sm font-bold text-[#03D26F] block">{invSnapshot.available_to_fulfil}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">On Hand</span>
                              <span className="text-sm font-semibold text-white block">{invSnapshot.current_stock}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">ROP Buffer</span>
                              <span className="text-sm font-semibold text-[#CEF431] block">{invSnapshot.reorder_point}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {!isUser && !decision && forecastSummary && (
                        <div className="p-3.5 rounded-xl bg-[#01272e] border border-cyan-500/30 shadow-md space-y-2">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-cyan-300 flex items-center gap-1.5">
                              <TrendingUp className="w-3.5 h-3.5" />
                              Demand Forecast • {forecastSummary.product_name}
                            </span>
                            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300">
                              {forecastSummary.forecast_horizon_days}d
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Forecast Total</span>
                              <span className="text-sm font-bold text-white block">{forecastSummary.total_forecasted_demand} units</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Model</span>
                              <span className="text-xs font-semibold text-cyan-200 truncate block mt-0.5">
                                {forecastSummary.selected_model_name || forecastSummary.selected_model}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}

                      {!isUser && !decision && stockoutSummary && (
                        <div className="p-3.5 rounded-xl bg-[#01272e] border border-amber-500/30 shadow-md space-y-2">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-amber-300 flex items-center gap-1.5">
                              <ShieldAlert className="w-3.5 h-3.5" />
                              Stockout Risk • {stockoutSummary.product_name}
                            </span>
                            <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-amber-500/20 text-amber-300">
                              {stockoutSummary.risk_level} Risk
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Exhaustion</span>
                              <span className="text-sm font-bold text-rose-300 block">
                                {stockoutSummary.days_until_stockout != null ? `~${stockoutSummary.days_until_stockout} Days` : 'N/A'}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Buffer Breach</span>
                              <span className="text-sm font-bold text-amber-300 block">
                                {stockoutSummary.days_until_buffer_breach === 0
                                  ? 'BREACHED NOW'
                                  : stockoutSummary.days_until_buffer_breach != null
                                  ? `~${stockoutSummary.days_until_buffer_breach} Days`
                                  : 'N/A'}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}

                      {!isUser && !decision && supplierOffer && (
                        <div className="p-3.5 rounded-xl bg-[#01272e] border border-cyan-500/30 shadow-md space-y-2">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-cyan-300 flex items-center gap-1.5">
                              <Truck className="w-3.5 h-3.5" />
                              Supplier Offer • {supplierOffer.supplier_name}
                            </span>
                            <span className="text-[10px] text-[#EAF4F4]/60">{supplierOffer.product_name}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Unit Cost</span>
                              <span className="text-sm font-bold text-[#03D26F] block">
                                {supplierOffer.unit_cost != null ? `LKR ${Number(supplierOffer.unit_cost).toLocaleString()}` : 'N/A'}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">MOQ</span>
                              <span className="text-sm font-semibold text-white block">{supplierOffer.moq ?? 'N/A'} u</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block font-sans">Lead Time</span>
                              <span className="text-sm font-semibold text-white block">{supplierOffer.lead_time_days ?? 'N/A'}d</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Text Bubble */}
                      {msg.content && (
                        <div
                          className={`p-3.5 rounded-2xl text-xs leading-relaxed ${
                            isUser
                              ? 'bg-[#01353e] text-white border border-white/[0.1] rounded-tr-none'
                              : 'bg-[#01272e] text-[#EAF4F4] border border-white/[0.08] rounded-tl-none shadow-sm'
                          }`}
                        >
                          {isUser ? (
                            <div className="whitespace-pre-wrap">{msg.content}</div>
                          ) : (
                            <ReactMarkdown
                              components={{
                                p: ({ node, ...props }) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
                                h1: ({ node, ...props }) => <h1 className="text-sm font-bold text-white mb-2 mt-2 first:mt-0" {...props} />,
                                h2: ({ node, ...props }) => <h2 className="text-xs font-bold text-white mb-1.5 mt-2 first:mt-0" {...props} />,
                                h3: ({ node, ...props }) => <h3 className="text-xs font-semibold text-[#03D26F] mb-1 mt-1.5 first:mt-0" {...props} />,
                                ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 mb-2 last:mb-0" {...props} />,
                                ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 mb-2 last:mb-0" {...props} />,
                                li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
                                strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
                                code: ({ node, inline, ...props }) =>
                                  inline ? (
                                    <code className="bg-black/30 px-1 py-0.5 rounded text-[11px] font-mono text-[#03D26F]" {...props} />
                                  ) : (
                                    <code className="block bg-black/40 p-2 rounded text-[11px] font-mono overflow-x-auto my-1.5" {...props} />
                                  ),
                                table: ({ node, ...props }) => (
                                  <div className="overflow-x-auto my-2">
                                    <table className="w-full text-left border-collapse border border-white/10 text-[11px]" {...props} />
                                  </div>
                                ),
                                th: ({ node, ...props }) => <th className="border border-white/10 px-2 py-1 bg-white/5 font-semibold text-white" {...props} />,
                                td: ({ node, ...props }) => <td className="border border-white/10 px-2 py-1" {...props} />,
                              }}
                            >
                              {msg.content}
                            </ReactMarkdown>
                          )}

                          {/* Clarification Chips */}
                          {!isUser && clarificationOptions && clarificationOptions.length > 0 && (
                            <div className="pt-2.5 mt-2 border-t border-white/[0.08] space-y-1.5">
                              <div className="text-[11px] text-[#EAF4F4]/70 font-medium">Quick options:</div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                {clarificationOptions.map((opt, i) => (
                                  <button
                                    key={i}
                                    onClick={() => {
                                      if (opt.value === 'custom' || opt.label.toLowerCase() === 'custom') {
                                        setCustomHorizonMsgId(msg.id);
                                      } else {
                                        handleSend(opt.value || opt.label);
                                      }
                                    }}
                                    disabled={loading}
                                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-[#03D26F]/15 hover:bg-[#03D26F]/30 text-[#03D26F] border border-[#03D26F]/40 transition-all cursor-pointer disabled:opacity-50"
                                  >
                                    {opt.label}
                                  </button>
                                ))}
                              </div>

                              {customHorizonMsgId === msg.id && (
                                <div className="mt-2 p-2 bg-black/40 border border-[#03D26F]/40 rounded-xl max-w-sm flex items-center gap-2">
                                  <span className="text-[11px] text-[#EAF4F4]/70 shrink-0">Days (1–90):</span>
                                  <input
                                    type="number"
                                    min={1}
                                    max={90}
                                    placeholder="e.g. 21"
                                    value={customHorizonInput}
                                    onChange={(e) => setCustomHorizonInput(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') handleCustomHorizonSubmit();
                                    }}
                                    autoFocus
                                    className="w-16 bg-black/60 border border-white/20 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-[#03D26F]"
                                  />
                                  <button
                                    onClick={handleCustomHorizonSubmit}
                                    disabled={loading}
                                    className="px-2.5 py-1 bg-[#03D26F] text-[#161514] font-bold text-xs rounded-lg hover:bg-[#02be63] transition-colors cursor-pointer"
                                  >
                                    Apply
                                  </button>
                                  <button
                                    onClick={() => setCustomHorizonMsgId(null)}
                                    className="text-[#EAF4F4]/50 hover:text-white text-xs px-1 cursor-pointer"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Standalone Sources link when not in a decision card */}
                      {!isUser && !decision && hasSources && (
                        <div className="pt-0.5">
                          <button
                            type="button"
                            onClick={() => toggleSources(msg.id)}
                            className="inline-flex items-center gap-1.5 text-[11px] text-[#03D26F] hover:underline font-medium cursor-pointer"
                          >
                            <FileText className="w-3 h-3" />
                            <span>
                              {isExpandedSources ? 'Hide Sources & Evidence' : `View Sources & Evidence (${sources.length})`}
                            </span>
                            {isExpandedSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>

                          {isExpandedSources && (
                            <div className="mt-2 space-y-2 p-3 bg-black/30 border border-white/[0.06] rounded-xl text-xs">
                              {sources.map((s, idx) => (
                                <div key={idx} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.05] space-y-1">
                                  <div className="flex items-center justify-between font-semibold text-white">
                                    <span>{s.document_title || s.label || 'Authoritative Source'}</span>
                                    <span className="text-[10px] text-[#CEF431] font-mono">
                                      {s.page_number ? `Page ${s.page_number}` : ''}
                                    </span>
                                  </div>
                                  {s.excerpt && (
                                    <p className="text-[11px] text-[#EAF4F4]/80 italic border-l-2 border-[#03D26F]/60 pl-2 mt-1">
                                      "{s.excerpt}"
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* User Avatar */}
                    {isUser && (
                      <div className="w-7 h-7 rounded-lg bg-blue-600/30 border border-blue-500/40 text-blue-300 flex items-center justify-center shrink-0 text-xs mt-0.5">
                        <UserIcon className="w-3.5 h-3.5" />
                      </div>
                    )}
                  </div>
                );
              })
            )}

            {/* Loading Indicator */}
            {loading && (
              <div className="flex gap-2.5 items-center text-xs text-[#03D26F] animate-pulse">
                <div className="w-7 h-7 rounded-lg bg-[#03D26F]/20 border border-[#03D26F]/40 flex items-center justify-center">
                  <Bot className="w-3.5 h-3.5 text-[#03D26F]" />
                </div>
                <span>SmartSupply multi-agent system analyzing...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mx-4 mb-2 p-2.5 rounded-xl bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="text-rose-300 hover:text-white cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Input Form */}
          <div className="p-3 sm:p-4 border-t border-white/[0.08] bg-[#01272e]/90">
            <div className="flex items-center gap-2 bg-[#01272e] border border-white/[0.1] focus-within:border-[#03D26F]/60 rounded-2xl px-3 py-2 transition-all shadow-inner">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask SmartSupply about inventory, demand, suppliers, or replenishment decisions..."
                rows={1}
                disabled={loading}
                className="flex-1 bg-transparent text-xs text-white placeholder-[#EAF4F4]/40 outline-none resize-none max-h-28 overflow-y-auto"
              />
              <button
                type="button"
                onClick={() => handleSend()}
                disabled={loading || !inputText.trim()}
                className="p-2 rounded-xl bg-[#03D26F] hover:bg-[#02be63] disabled:opacity-40 text-[#161514] transition-all shrink-0 font-semibold cursor-pointer"
                title="Send message (Enter)"
              >
                <Send className="w-4 h-4 text-[#161514]" />
              </button>
            </div>
            <div className="text-[10px] text-[#EAF4F4]/40 text-center mt-1.5 font-mono">
              SmartSupply AI Assistant is read-only decision support verified against PostgreSQL and Document IR.
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
