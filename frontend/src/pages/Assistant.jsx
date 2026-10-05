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
  Menu,
  X,
  Package,
  TrendingUp,
  ShieldAlert,
  Truck,
  CheckCircle2,
  Info,
  Calendar,
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

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Load conversations on mount
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

    // If no conversation exists yet, create one first
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

    // Optimistically append user message
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

      // Refresh conversations list to update title and timestamps
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

  return (
    <div className="min-h-screen bg-[#00171B] text-[#EAF4F4] flex flex-col font-sans">
      <Navbar />

      <div className="flex-1 flex overflow-hidden relative max-w-7xl w-full mx-auto p-2 sm:p-4 gap-4">
        {/* Mobile Sidebar Toggle Button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="lg:hidden fixed bottom-20 right-4 z-40 bg-[#03D26F] text-[#00171B] p-3 rounded-full shadow-lg hover:bg-[#02b35d] transition-all"
          title="Toggle Conversations"
        >
          {sidebarOpen ? <X className="w-6 h-6" /> : <Layers className="w-6 h-6" />}
        </button>

        {/* Sidebar: Conversations List */}
        <aside
          className={`fixed lg:static inset-y-0 left-0 z-30 w-72 sm:w-80 bg-[#01272e]/95 lg:bg-[#01272e]/70 backdrop-blur-xl border border-white/[0.08] rounded-2xl flex flex-col transition-transform duration-300 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          }`}
        >
          {/* Sidebar Header */}
          <div className="p-4 border-b border-white/[0.08] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-[#03D26F]" />
              <h2 className="font-semibold text-sm tracking-wide text-white">Conversations</h2>
            </div>
            <button
              onClick={() => handleNewChat()}
              className="inline-flex items-center gap-1.5 text-xs bg-[#03D26F]/20 hover:bg-[#03D26F]/30 text-[#03D26F] border border-[#03D26F]/40 px-2.5 py-1.5 rounded-lg transition-all font-medium"
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
                No past conversations. Start a new chat!
              </div>
            ) : (
              conversations.map((conv) => {
                const isActive = conv.id === activeConversationId;
                return (
                  <div
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    className={`group relative flex items-center justify-between p-3 rounded-xl cursor-pointer text-xs transition-all ${
                      isActive
                        ? 'bg-[#03D26F]/15 border border-[#03D26F]/40 text-white font-medium shadow-sm'
                        : 'hover:bg-white/[0.04] text-[#EAF4F4]/80 border border-transparent'
                    }`}
                  >
                    <div className="flex-1 min-w-0 pr-2">
                      <div className="truncate font-semibold">{conv.title || 'Conversation'}</div>
                      {conv.last_message && (
                        <div className="text-[10px] text-[#EAF4F4]/50 truncate mt-0.5">
                          {conv.last_message}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      className="opacity-0 group-hover:opacity-100 hover:text-red-400 p-1 rounded transition-opacity"
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

        {/* Main Chat Interface */}
        <main className="flex-1 flex flex-col bg-[#01272e]/50 backdrop-blur-xl border border-white/[0.08] rounded-2xl overflow-hidden shadow-2xl relative">
          {/* Top Bar */}
          <div className="px-5 py-3.5 border-b border-white/[0.08] flex items-center justify-between bg-[#01272e]/90">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#03D26F]/20 border border-[#03D26F]/40 flex items-center justify-center">
                <Bot className="w-4 h-4 text-[#03D26F]" />
              </div>
              <div>
                <h1 className="text-sm font-semibold text-white tracking-wide flex items-center gap-2">
                  SmartSupply AI Assistant
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-[#03D26F]/10 text-[#03D26F] border border-[#03D26F]/30">
                    Live Agents Active
                  </span>
                </h1>
                <p className="text-[10px] text-[#EAF4F4]/60">
                  Grounded multi-agent intelligence across Inventory, Demand, Suppliers & Policy
                </p>
              </div>
            </div>
          </div>

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {messages.length === 0 && !loading ? (
              // Empty State / Starter Suggestions
              <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto my-auto p-6">
                <div className="w-14 h-14 rounded-2xl bg-[#03D26F]/10 border border-[#03D26F]/30 flex items-center justify-center mb-4 shadow-lg shadow-[#03D26F]/5">
                  <Sparkles className="w-7 h-7 text-[#03D26F]" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">How can I assist your supply chain today?</h3>
                <p className="text-xs text-[#EAF4F4]/70 mb-6 leading-relaxed">
                  Ask me about real-time inventory positions, demand forecasts, supplier commercial terms,
                  SLA delivery contracts, or complete replenishment recommendations.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
                  {STARTER_PROMPTS.map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(prompt)}
                      className="p-3 bg-[#01353e]/60 hover:bg-[#01353e] border border-white/[0.08] hover:border-[#03D26F]/40 rounded-xl text-xs text-[#EAF4F4]/90 transition-all flex items-center justify-between group"
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
                    className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
                  >
                    {/* Avatar */}
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs ${
                        isUser
                          ? 'bg-blue-600/30 border border-blue-500/40 text-blue-300'
                          : 'bg-[#03D26F]/20 border border-[#03D26F]/40 text-[#03D26F]'
                      }`}
                    >
                      {isUser ? <UserIcon className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                    </div>

                    {/* Content Box */}
                    <div className="space-y-2 max-w-[85%] sm:max-w-xl">
                      {/* Degraded State Banner */}
                      {!isUser && isDegraded && (
                        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs">
                          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                          <span>
                            Natural-language synthesis is temporarily unavailable; authoritative SmartSupply data is shown below.
                          </span>
                        </div>
                      )}

                      {/* Clarification State Banner */}
                      {!isUser && isClarification && (
                        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-200 text-xs">
                          <HelpCircle className="w-4 h-4 shrink-0 text-[#03D26F]" />
                          <span>Parameter clarification requested to ensure accurate analysis.</span>
                        </div>
                      )}

                      {/* 1. Full Replenishment Recommendation Card */}
                      {!isUser && decision && (
                        <div className="p-4 rounded-xl bg-[#002B32] border border-[#03D26F]/40 shadow-md space-y-3">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-2">
                            <span className="text-xs uppercase tracking-wider font-bold text-[#03D26F] flex items-center gap-1.5">
                              <Package className="w-3.5 h-3.5" />
                              Replenishment Recommendation
                            </span>
                            <span
                              className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                                decision.urgency === 'EMERGENCY'
                                  ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                                  : decision.urgency === 'HIGH'
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                  : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              }`}
                            >
                              {decision.urgency} Urgency
                            </span>
                          </div>

                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                            <div className="p-2 rounded bg-black/20">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Target Product</span>
                              <span className="font-semibold text-white truncate block">{decision.product_name}</span>
                            </div>
                            <div className="p-2 rounded bg-black/20">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Recommended Order</span>
                              <span className="font-semibold text-[#03D26F] text-sm block">
                                {decision.recommended_order_quantity} units
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/20">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Required Delivery</span>
                              <span className="font-semibold text-white block">
                                ≤ {decision.required_delivery_window_days} days
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/20">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Designated Supplier</span>
                              <span className="font-semibold text-white truncate block">
                                {decision.selected_supplier_name || 'N/A'}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/20">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Lead Time / Slack</span>
                              <span className="font-semibold text-white block">
                                {decision.lead_time_days ?? 'N/A'}d (Slack: {decision.delivery_slack_days ?? 0}d)
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/20">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Estimated Spend</span>
                              <span className="font-semibold text-white block">
                                {decision.estimated_total_cost ? `LKR ${decision.estimated_total_cost.toLocaleString()}` : 'N/A'}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 2. Compact INVENTORY SNAPSHOT Card */}
                      {!isUser && invSnapshot && (
                        <div className="p-3.5 rounded-xl bg-[#002730] border border-[#03D26F]/30 shadow-md space-y-2.5">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-[#03D26F] flex items-center gap-1.5">
                              <Package className="w-3.5 h-3.5" />
                              Inventory Snapshot • {invSnapshot.product_name}
                            </span>
                            <span className="text-[10px] font-semibold text-[#EAF4F4]/60">Real-time Stock</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="p-2 rounded bg-black/25 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Available to Fulfil</span>
                              <span className="text-sm font-bold text-[#03D26F] block">{invSnapshot.available_to_fulfil}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">On Hand</span>
                              <span className="text-sm font-semibold text-white block">{invSnapshot.current_stock}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Reserved</span>
                              <span className="text-sm font-semibold text-amber-300 block">{invSnapshot.reserved_stock}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Incoming</span>
                              <span className="text-sm font-semibold text-blue-300 block">{invSnapshot.incoming_stock}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Effective Stock</span>
                              <span className="text-sm font-semibold text-white block">{invSnapshot.effective_inventory}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25 border border-white/[0.04]">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">ROP Buffer</span>
                              <span className="text-sm font-semibold text-white block">{invSnapshot.reorder_point}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 3. Compact DEMAND FORECAST Card */}
                      {!isUser && forecastSummary && (
                        <div className="p-3.5 rounded-xl bg-[#002730] border border-blue-500/30 shadow-md space-y-2.5">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-blue-400 flex items-center gap-1.5">
                              <TrendingUp className="w-3.5 h-3.5" />
                              Demand Forecast • {forecastSummary.product_name}
                            </span>
                            <span className="text-[10px] font-semibold bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30">
                              {forecastSummary.forecast_horizon_days} Days Horizon
                            </span>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Forecast Demand</span>
                              <span className="text-sm font-bold text-blue-300 block">{forecastSummary.total_forecasted_demand} units</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Daily Average</span>
                              <span className="text-sm font-semibold text-white block">{forecastSummary.average_daily_demand}/day</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Forecast Model</span>
                              <span className="text-xs font-semibold text-white truncate block">{forecastSummary.selected_model_name || forecastSummary.selected_model}</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Demand Risk</span>
                              <span className="text-xs font-semibold text-amber-300 uppercase block">{forecastSummary.demand_risk_level}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 4. Compact STOCKOUT RISK Card */}
                      {!isUser && stockoutSummary && (
                        <div className="p-3.5 rounded-xl bg-[#002730] border border-amber-500/30 shadow-md space-y-2.5">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-amber-400 flex items-center gap-1.5">
                              <ShieldAlert className="w-3.5 h-3.5" />
                              Stockout Risk • {stockoutSummary.product_name}
                            </span>
                            <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                              stockoutSummary.risk_level === 'HIGH' || stockoutSummary.risk_level === 'CRITICAL'
                                ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                                : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            }`}>
                              {stockoutSummary.risk_level} Risk
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Planning Horizon</span>
                              <span className="text-sm font-semibold text-white block">{stockoutSummary.forecast_horizon_days} Days</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Inventory Exhaustion</span>
                              <span className="text-sm font-bold text-red-300 block">
                                {stockoutSummary.days_until_stockout != null ? `~${stockoutSummary.days_until_stockout} Days` : 'N/A'}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Buffer Breach</span>
                              <span className="text-sm font-semibold text-amber-300 block">
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

                      {/* 5. Compact SUPPLIER OFFER Card */}
                      {!isUser && supplierOffer && (
                        <div className="p-3.5 rounded-xl bg-[#002730] border border-cyan-500/30 shadow-md space-y-2.5">
                          <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
                            <span className="text-xs uppercase tracking-wider font-bold text-cyan-400 flex items-center gap-1.5">
                              <Truck className="w-3.5 h-3.5" />
                              Supplier Offer • {supplierOffer.supplier_name}
                            </span>
                            <span className="text-[10px] font-semibold text-[#EAF4F4]/60">{supplierOffer.product_name}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Unit Cost</span>
                              <span className="text-sm font-bold text-[#03D26F] block">
                                {supplierOffer.unit_cost != null ? `LKR ${Number(supplierOffer.unit_cost).toLocaleString()}` : 'N/A'}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">MOQ</span>
                              <span className="text-sm font-semibold text-white block">{supplierOffer.moq ?? 'N/A'} units</span>
                            </div>
                            <div className="p-2 rounded bg-black/25">
                              <span className="text-[10px] text-[#EAF4F4]/60 block">Lead Time</span>
                              <span className="text-sm font-semibold text-white block">{supplierOffer.lead_time_days ?? 'N/A'} days</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Main Message Bubble with Safe Markdown Rendering */}
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
                              h1: ({ node, ...props }) => <h1 className="text-sm font-bold text-white mb-2 mt-3 first:mt-0" {...props} />,
                              h2: ({ node, ...props }) => <h2 className="text-xs font-bold text-white mb-2 mt-2 first:mt-0" {...props} />,
                              h3: ({ node, ...props }) => <h3 className="text-xs font-semibold text-[#03D26F] mb-1.5 mt-2 first:mt-0 uppercase tracking-wider" {...props} />,
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

                        {/* Clarification Quick Reply Buttons / Horizon Chips */}
                        {!isUser && clarificationOptions && clarificationOptions.length > 0 && (
                          <div className="pt-3 mt-2 border-t border-white/[0.08] space-y-2">
                            <div className="text-[11px] text-[#EAF4F4]/70 font-medium">Quick options:</div>
                            <div className="flex flex-wrap items-center gap-2">
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
                                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#03D26F]/15 hover:bg-[#03D26F]/30 text-[#03D26F] border border-[#03D26F]/40 hover:border-[#03D26F] transition-all cursor-pointer shadow-sm active:scale-95 disabled:opacity-50"
                                >
                                  {opt.label}
                                </button>
                              ))}
                            </div>

                            {/* Inline Custom Horizon Input */}
                            {customHorizonMsgId === msg.id && (
                              <div className="mt-2.5 p-2.5 bg-black/40 border border-[#03D26F]/40 rounded-xl max-w-sm flex items-center gap-2 animate-fadeIn">
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
                                  className="w-20 bg-black/60 border border-white/20 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-[#03D26F]"
                                />
                                <button
                                  onClick={handleCustomHorizonSubmit}
                                  disabled={loading}
                                  className="px-2.5 py-1 bg-[#03D26F] text-[#00171B] font-bold text-xs rounded-lg hover:bg-[#02b35d] transition-colors"
                                >
                                  Apply
                                </button>
                                <button
                                  onClick={() => setCustomHorizonMsgId(null)}
                                  className="text-[#EAF4F4]/50 hover:text-white text-xs px-1"
                                >
                                  Cancel
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Progressive Disclosure Sections for Full Replenishment Decisions */}
                      {!isUser && decision && decisionDetails && (
                        <div className="space-y-1.5 pt-1">
                          {/* Accordion 1: Inventory & Demand Details */}
                          {decisionDetails.inventory_demand && (
                            <div className="border border-white/[0.06] rounded-xl overflow-hidden bg-black/20">
                              <button
                                onClick={() => toggleSection(`${msg.id}-inv_demand`)}
                                className="w-full px-3 py-2 text-left flex items-center justify-between text-[11px] font-semibold text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.02] transition-colors"
                              >
                                <span className="flex items-center gap-1.5">
                                  <Package className="w-3.5 h-3.5 text-[#03D26F]" />
                                  Inventory & Demand Details
                                </span>
                                {expandedSections[`${msg.id}-inv_demand`] ? (
                                  <ChevronUp className="w-3.5 h-3.5 text-[#03D26F]" />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                )}
                              </button>
                              {expandedSections[`${msg.id}-inv_demand`] && (
                                <div className="p-3 text-[11px] space-y-2 border-t border-white/[0.06] bg-black/30">
                                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                    <div className="p-1.5 rounded bg-white/[0.02]">
                                      <span className="text-[#EAF4F4]/50 text-[10px] block">Forecast Demand</span>
                                      <span className="font-semibold text-white">
                                        {decisionDetails.inventory_demand.total_forecasted_demand} units ({decisionDetails.inventory_demand.selected_model})
                                      </span>
                                    </div>
                                    <div className="p-1.5 rounded bg-white/[0.02]">
                                      <span className="text-[#EAF4F4]/50 text-[10px] block">Lead Time Demand</span>
                                      <span className="font-semibold text-white">
                                        {decisionDetails.inventory_demand.expected_demand_over_lead_time} units
                                      </span>
                                    </div>
                                    <div className="p-1.5 rounded bg-white/[0.02]">
                                      <span className="text-[#EAF4F4]/50 text-[10px] block">Effective Stock</span>
                                      <span className="font-semibold text-white">
                                        {decisionDetails.inventory_demand.effective_inventory} units
                                      </span>
                                    </div>
                                    <div className="p-1.5 rounded bg-white/[0.02]">
                                      <span className="text-[#EAF4F4]/50 text-[10px] block">Inventory Exhaustion</span>
                                      <span className="font-semibold text-red-300">
                                        {decisionDetails.inventory_demand.days_until_stockout != null
                                          ? `~${decisionDetails.inventory_demand.days_until_stockout} days`
                                          : 'N/A'}
                                      </span>
                                    </div>
                                    <div className="p-1.5 rounded bg-white/[0.02]">
                                      <span className="text-[#EAF4F4]/50 text-[10px] block">Buffer Breach</span>
                                      <span className="font-semibold text-amber-300">
                                        {decisionDetails.inventory_demand.days_until_buffer_breach === 0
                                          ? 'BREACHED NOW'
                                          : decisionDetails.inventory_demand.days_until_buffer_breach != null
                                            ? `~${decisionDetails.inventory_demand.days_until_buffer_breach} days`
                                            : 'N/A'}
                                      </span>
                                    </div>
                                    <div className="p-1.5 rounded bg-white/[0.02]">
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
                          {decisionDetails.supplier_comparison && decisionDetails.supplier_comparison.length > 0 && (
                            <div className="border border-white/[0.06] rounded-xl overflow-hidden bg-black/20">
                              <button
                                onClick={() => toggleSection(`${msg.id}-sup_compare`)}
                                className="w-full px-3 py-2 text-left flex items-center justify-between text-[11px] font-semibold text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.02] transition-colors"
                              >
                                <span className="flex items-center gap-1.5">
                                  <Truck className="w-3.5 h-3.5 text-blue-400" />
                                  Supplier Comparison ({decisionDetails.supplier_comparison.length})
                                </span>
                                {expandedSections[`${msg.id}-sup_compare`] ? (
                                  <ChevronUp className="w-3.5 h-3.5 text-blue-400" />
                                ) : (
                                  <ChevronDown className="text-[#EAF4F4]/50 w-3.5 h-3.5" />
                                )}
                              </button>
                              {expandedSections[`${msg.id}-sup_compare`] && (
                                <div className="p-2.5 text-[11px] border-t border-white/[0.06] bg-black/30 overflow-x-auto">
                                  <table className="w-full text-left border-collapse text-[10px]">
                                    <thead>
                                      <tr className="border-b border-white/10 text-[#EAF4F4]/60">
                                        <th className="py-1 px-1.5">Supplier</th>
                                        <th className="py-1 px-1.5">Cost</th>
                                        <th className="py-1 px-1.5">MOQ</th>
                                        <th className="py-1 px-1.5">Lead Time</th>
                                        <th className="py-1 px-1.5">Slack</th>
                                        <th className="py-1 px-1.5">Score</th>
                                        <th className="py-1 px-1.5">Status</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/[0.04]">
                                      {decisionDetails.supplier_comparison.map((sup, idx) => (
                                        <tr key={idx} className={sup.selected ? 'bg-[#03D26F]/10 text-white font-semibold' : 'text-[#EAF4F4]/80'}>
                                          <td className="py-1 px-1.5 truncate max-w-[120px]">
                                            {sup.supplier_name} {sup.selected ? '✓' : ''}
                                          </td>
                                          <td className="py-1 px-1.5">{sup.unit_cost != null ? `LKR ${Number(sup.unit_cost).toLocaleString()}` : '—'}</td>
                                          <td className="py-1 px-1.5">{sup.moq ?? '—'}</td>
                                          <td className="py-1 px-1.5">{sup.lead_time_days ?? '—'}d</td>
                                          <td className="py-1 px-1.5">{sup.delivery_slack_days ?? '—'}d</td>
                                          <td className="py-1 px-1.5">{sup.weighted_score != null ? Number(sup.weighted_score).toFixed(1) : '—'}</td>
                                          <td className="py-1 px-1.5">
                                            {sup.selected ? (
                                              <span className="text-[#03D26F] text-[9px] uppercase font-bold">Selected</span>
                                            ) : sup.is_feasible ? (
                                              <span className="text-blue-300 text-[9px]">Eligible</span>
                                            ) : (
                                              <span className="text-red-400 text-[9px]">Disqualified</span>
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

                          {/* Accordion 3: Decision Reasoning */}
                          {decisionDetails.factors && decisionDetails.factors.length > 0 && (
                            <div className="border border-white/[0.06] rounded-xl overflow-hidden bg-black/20">
                              <button
                                onClick={() => toggleSection(`${msg.id}-factors`)}
                                className="w-full px-3 py-2 text-left flex items-center justify-between text-[11px] font-semibold text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.02] transition-colors"
                              >
                                <span className="flex items-center gap-1.5">
                                  <Info className="w-3.5 h-3.5 text-cyan-400" />
                                  Decision Factors ({decisionDetails.factors.length})
                                </span>
                                {expandedSections[`${msg.id}-factors`] ? (
                                  <ChevronUp className="w-3.5 h-3.5 text-cyan-400" />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                )}
                              </button>
                              {expandedSections[`${msg.id}-factors`] && (
                                <div className="p-3 text-[11px] space-y-1.5 border-t border-white/[0.06] bg-black/30">
                                  <ul className="list-disc pl-4 space-y-1 text-[#EAF4F4]/90">
                                    {decisionDetails.factors.map((f, i) => (
                                      <li key={i}>{f}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Accordion 4: Assumptions & Warnings */}
                          {decisionDetails.warnings && decisionDetails.warnings.length > 0 && (
                            <div className="border border-white/[0.06] rounded-xl overflow-hidden bg-black/20">
                              <button
                                onClick={() => toggleSection(`${msg.id}-warnings`)}
                                className="w-full px-3 py-2 text-left flex items-center justify-between text-[11px] font-semibold text-amber-300 hover:text-amber-200 hover:bg-white/[0.02] transition-colors"
                              >
                                <span className="flex items-center gap-1.5">
                                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                                  Assumptions & Warnings ({decisionDetails.warnings.length})
                                </span>
                                {expandedSections[`${msg.id}-warnings`] ? (
                                  <ChevronUp className="w-3.5 h-3.5 text-amber-400" />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5 text-[#EAF4F4]/50" />
                                )}
                              </button>
                              {expandedSections[`${msg.id}-warnings`] && (
                                <div className="p-3 text-[11px] space-y-1 border-t border-white/[0.06] bg-black/30 text-amber-200/90">
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
                      )}

                      {/* Sources / Evidence Accordion */}
                      {!isUser && hasSources && (
                        <div className="pt-1">
                          <button
                            onClick={() => toggleSources(msg.id)}
                            className="inline-flex items-center gap-1.5 text-[11px] text-[#03D26F] hover:underline font-medium cursor-pointer"
                          >
                            <FileText className="w-3 h-3" />
                            <span>
                              {isExpandedSources ? 'Hide Sources & Evidence' : `View Grounded Sources & Evidence (${sources.length})`}
                            </span>
                            {isExpandedSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>

                          {isExpandedSources && (
                            <div className="mt-2 space-y-2 p-3 bg-black/30 border border-white/[0.06] rounded-xl text-[11px]">
                              {sources.map((s, idx) => (
                                <div key={idx} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.05] space-y-1">
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                      {s.source_type === 'document_ir' ? (
                                        <FileText className="w-3 h-3 text-[#03D26F]" />
                                      ) : (
                                        <Database className="w-3 h-3 text-blue-400" />
                                      )}
                                      <span className="font-semibold text-white">
                                        {s.document_title || s.label || 'Authoritative Source'}
                                      </span>
                                    </div>
                                    <span
                                      className={`text-[9px] uppercase px-1.5 py-0.5 rounded font-bold ${
                                        s.authority === 'operational'
                                          ? 'bg-blue-500/20 text-blue-300'
                                          : 'bg-emerald-500/20 text-emerald-300'
                                      }`}
                                    >
                                      {s.authority}
                                    </span>
                                  </div>

                                  {s.page_number && (
                                    <div className="text-[10px] text-[#EAF4F4]/50">
                                      Page {s.page_number} {s.document_type ? `• ${s.document_type}` : ''}
                                    </div>
                                  )}

                                  {s.excerpt && (
                                    <p className="text-[10px] text-[#EAF4F4]/80 italic border-l-2 border-[#03D26F]/50 pl-2 mt-1">
                                      "{s.excerpt}"
                                    </p>
                                  )}

                                  {s.fields && (
                                    <div className="flex flex-wrap gap-2 text-[10px] text-[#EAF4F4]/70 pt-0.5">
                                      {Object.entries(s.fields).map(([k, v]) => (
                                        <span key={k} className="bg-white/[0.04] px-1.5 py-0.5 rounded">
                                          {k}: <b className="text-white">{String(v)}</b>
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {/* Loading Indicator */}
            {loading && (
              <div className="flex gap-3 items-center text-xs text-[#03D26F] animate-pulse">
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
            <div className="mx-4 mb-2 p-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-200 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="text-red-300 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Input Form */}
          <div className="p-3 sm:p-4 border-t border-white/[0.08] bg-[#01272e]/90">
            <div className="flex items-center gap-2 bg-[#00171B] border border-white/[0.1] focus-within:border-[#03D26F]/60 rounded-2xl px-3 py-2 transition-all shadow-inner">
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
                onClick={() => handleSend()}
                disabled={loading || !inputText.trim()}
                className="p-2 rounded-xl bg-[#03D26F] hover:bg-[#02b35d] disabled:opacity-40 disabled:hover:bg-[#03D26F] text-[#00171B] transition-all shrink-0 font-semibold"
                title="Send message (Enter)"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <div className="text-[10px] text-[#EAF4F4]/40 text-center mt-1.5">
              SmartSupply AI Assistant is read-only decision support. Operational facts are verified against PostgreSQL and Document IR.
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
