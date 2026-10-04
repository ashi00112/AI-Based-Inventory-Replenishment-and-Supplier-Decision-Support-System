import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Package,
  Boxes,
  ArrowRightLeft,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Plus,
  ArrowUpRight,
  Warehouse,
  RefreshCw,
  Clock,
  Sparkles,
  Sliders,
  RotateCcw,
  Users,
  ShieldCheck,
  Cpu,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getProducts } from '../services/productApi';
import { getInventory } from '../services/inventoryApi';
import { getInventoryTransactions } from '../services/inventoryTransactionApi';
import Navbar from '../components/Navbar';

export default function Dashboard() {
  const { user, isAdmin } = useAuth();

  // State
  const [products, setProducts] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Load live system operational data
  const loadDashboardData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    else setIsLoading(true);

    try {
      const [prodRes, invRes, txRes] = await Promise.all([
        getProducts({ limit: 500 }),
        getInventory({ limit: 500 }),
        getInventoryTransactions({ limit: 6 }),
      ]);

      if (prodRes.success) setProducts(prodRes.data || []);
      if (invRes.success) setInventory(invRes.data || []);
      if (txRes.success) setRecentTransactions(txRes.data || []);
    } catch (err) {
      console.error('Failed to load dashboard operational data:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Operational Metrics Computation
  const metrics = useMemo(() => {
    const totalProducts = products.length;
    let totalOnHand = 0;
    let totalReserved = 0;
    let totalAvailable = 0;
    const lowStockItems = [];

    for (const item of inventory) {
      const onHand = item.on_hand || 0;
      const reserved = item.reserved || 0;
      const available = item.available_stock || 0;
      const rop = item.product?.reorder_point ?? 0;

      totalOnHand += onHand;
      totalReserved += reserved;
      totalAvailable += available;

      if (available <= rop) {
        lowStockItems.push(item);
      }
    }

    return {
      totalProducts,
      totalOnHand,
      totalReserved,
      totalAvailable,
      lowStockCount: lowStockItems.length,
      lowStockItems: lowStockItems.slice(0, 5),
    };
  }, [products, inventory]);

  const renderTxBadge = (type) => {
    switch (type) {
      case 'sale':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 font-mono border border-cyan-500/20">
            <TrendingDown className="w-2.5 h-2.5" /> SALE
          </span>
        );
      case 'restock':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#03D26F]/15 text-[#03D26F] font-mono border border-[#03D26F]/25">
            <TrendingUp className="w-2.5 h-2.5" /> RESTOCK
          </span>
        );
      case 'return':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-300 font-mono border border-sky-500/20">
            <RotateCcw className="w-2.5 h-2.5" /> RETURN
          </span>
        );
      case 'adjustment':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#CEF431]/15 text-[#CEF431] font-mono border border-[#CEF431]/25">
            <Sliders className="w-2.5 h-2.5" /> ADJUST
          </span>
        );
      default:
        return <span className="text-[10px] font-mono text-[#EAF4F4]/50">{type}</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col font-sans selection:bg-[#03D26F]/30 selection:text-white">
      <Navbar />

      {/* Main Operational Dashboard Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Welcome Hero Banner with Dashboard Network Asset */}
        <section className="relative overflow-hidden rounded-3xl bg-[#01353e] border border-white/[0.1] p-6 sm:p-8 lg:p-10 shadow-xl">
          {/* Subtle Background Layer */}
          <div
            className="absolute inset-0 bg-cover bg-center opacity-30 mix-blend-luminosity scale-105 pointer-events-none"
            style={{ backgroundImage: `url('/assets/dashboard-hero.jpg')` }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#01272e] via-[#01353e]/90 to-[#014651]/80 pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="max-w-2xl space-y-3">
              <div className="inline-flex items-center gap-2 text-xs font-semibold px-3 py-1 rounded-full bg-[#03D26F]/15 border border-[#03D26F]/30 text-[#03D26F]">
                <Cpu className="w-3.5 h-3.5" />
                <span>Autonomous Multi-Agent Workspace</span>
              </div>
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black text-white tracking-tight">
                Welcome back, {user?.name || 'Supply Manager'}
              </h1>
              <p className="text-xs sm:text-sm text-[#EAF4F4]/80 leading-relaxed">
                Live monitoring of multi-warehouse physical stock, safety reorder thresholds, and autonomous procurement reasoning. All agent decisions are human-supervised with strict enterprise RBAC.
              </p>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap items-center gap-3 shrink-0">
              <button
                onClick={() => loadDashboardData(true)}
                disabled={isRefreshing}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#01272e]/80 hover:bg-[#01272e] border border-white/[0.1] text-[#EAF4F4] text-xs font-medium transition disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                <span>Refresh Live Data</span>
              </button>

              <Link
                to="/transactions"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#03D26F] hover:bg-[#02be63] text-[#161514] font-bold text-xs transition shadow-lg shadow-[#03D26F]/20 cursor-pointer"
              >
                <Plus className="w-4 h-4 text-[#161514]" />
                <span>Record Movement</span>
              </Link>

              <Link
                to="/decisions"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#CEF431] hover:bg-[#bde026] text-[#161514] font-bold text-xs transition shadow-lg shadow-[#CEF431]/20 cursor-pointer"
              >
                <Sparkles className="w-4 h-4 text-[#161514]" />
                <span>Run Decision Agent</span>
              </Link>
            </div>
          </div>
        </section>

        {/* Live Operational KPI Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Catalog Products */}
          <Link
            to="/products"
            className="group bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-[#03D26F]/40 rounded-2xl p-5 transition-all flex flex-col justify-between shadow-sm"
          >
            <div className="flex items-center justify-between text-[#EAF4F4]/70">
              <span className="text-xs font-semibold uppercase tracking-wider">Catalog Products</span>
              <div className="p-2 rounded-xl bg-[#03D26F]/10 text-[#03D26F] group-hover:scale-105 transition">
                <Package className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-black font-mono text-white">
                {isLoading ? '—' : metrics.totalProducts}
              </span>
              <span className="text-xs text-[#03D26F] font-semibold inline-flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                Manage <ArrowUpRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>

          {/* 2. On-Hand Physical Stock */}
          <Link
            to="/inventory"
            className="group bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-[#03D26F]/40 rounded-2xl p-5 transition-all flex flex-col justify-between shadow-sm"
          >
            <div className="flex items-center justify-between text-[#EAF4F4]/70">
              <span className="text-xs font-semibold uppercase tracking-wider">Total On Hand</span>
              <div className="p-2 rounded-xl bg-[#03D26F]/15 text-[#03D26F] group-hover:scale-105 transition">
                <Warehouse className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-black font-mono text-[#03D26F]">
                {isLoading ? '—' : metrics.totalOnHand.toLocaleString()}
              </span>
              <span className="text-[11px] text-[#EAF4F4]/60 font-medium">units stored</span>
            </div>
          </Link>

          {/* 3. Reserved Orders */}
          <Link
            to="/inventory"
            className="group bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-cyan-400/40 rounded-2xl p-5 transition-all flex flex-col justify-between shadow-sm"
          >
            <div className="flex items-center justify-between text-[#EAF4F4]/70">
              <span className="text-xs font-semibold uppercase tracking-wider">Committed / Reserved</span>
              <div className="p-2 rounded-xl bg-cyan-500/15 text-cyan-300 group-hover:scale-105 transition">
                <Boxes className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-black font-mono text-cyan-200">
                {isLoading ? '—' : metrics.totalReserved.toLocaleString()}
              </span>
              <span className="text-[11px] text-[#EAF4F4]/60 font-medium">
                Avail: {metrics.totalAvailable.toLocaleString()}
              </span>
            </div>
          </Link>

          {/* 4. Low Stock Alerts */}
          <Link
            to="/inventory"
            className="group bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-[#CEF431]/40 rounded-2xl p-5 transition-all flex flex-col justify-between shadow-sm"
          >
            <div className="flex items-center justify-between text-[#EAF4F4]/70">
              <span className="text-xs font-semibold uppercase tracking-wider">Reorder Attention</span>
              <div className="p-2 rounded-xl bg-[#CEF431]/15 text-[#CEF431] group-hover:scale-105 transition">
                <AlertTriangle className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-black font-mono text-[#CEF431]">
                {isLoading ? '—' : metrics.lowStockCount}
              </span>
              <span className="text-[11px] font-semibold text-[#CEF431]/80">
                {metrics.lowStockCount === 0 ? 'Stock healthy' : 'Below safety threshold'}
              </span>
            </div>
          </Link>
        </section>

        {/* Core Operational Panels */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Recent Stock Movement Ledger */}
          <div className="lg:col-span-2 bg-[#01353e]/50 border border-white/[0.08] rounded-2xl p-5 sm:p-6 flex flex-col justify-between space-y-4 backdrop-blur-md">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <ArrowRightLeft className="w-4 h-4 text-[#03D26F]" />
                  Recent Stock Movements
                </h2>
                <p className="text-[11px] text-[#EAF4F4]/60 mt-0.5">
                  Latest verified and immutable warehouse transactions
                </p>
              </div>
              <Link
                to="/transactions"
                className="text-xs font-semibold text-[#03D26F] hover:text-[#02be63] inline-flex items-center gap-1 transition"
              >
                Full Ledger <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Transaction List */}
            <div className="divide-y divide-white/[0.06]">
              {isLoading ? (
                <div className="py-12 text-center text-[#EAF4F4]/50 flex flex-col items-center gap-2">
                  <Clock className="w-5 h-5 animate-spin text-[#03D26F]" />
                  <span className="text-xs">Loading movements...</span>
                </div>
              ) : recentTransactions.length === 0 ? (
                <div className="py-12 text-center text-[#EAF4F4]/50 flex flex-col items-center gap-2">
                  <ArrowRightLeft className="w-7 h-7 text-[#EAF4F4]/30" />
                  <span className="text-xs">No stock transactions logged yet.</span>
                  <Link
                    to="/transactions"
                    className="text-xs text-[#03D26F] hover:underline mt-1 font-semibold"
                  >
                    Record the first transaction →
                  </Link>
                </div>
              ) : (
                recentTransactions.map((tx) => (
                  <div key={tx.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                    <div className="flex items-center gap-3 min-w-0">
                      {renderTxBadge(tx.transaction_type)}
                      <div className="min-w-0">
                        <p className="font-semibold text-white truncate">
                          {tx.product?.name || `Product #${tx.product_id}`}
                        </p>
                        <p className="text-[10px] text-[#EAF4F4]/50 font-mono">
                          SKU: {tx.product?.sku} • {new Date(tx.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="font-mono font-bold text-white text-xs block">
                        {tx.transaction_type === 'sale'
                          ? `-${tx.quantity}`
                          : tx.transaction_type === 'adjustment' && tx.quantity > 0
                          ? `+${tx.quantity}`
                          : tx.quantity > 0
                          ? `+${tx.quantity}`
                          : tx.quantity}
                      </span>
                      <span className="text-[10px] font-mono text-[#EAF4F4]/50">
                        {tx.previous_on_hand} → {tx.new_on_hand}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right Column: Low Stock Threshold Monitor */}
          <div className="bg-[#01353e]/50 border border-white/[0.08] rounded-2xl p-5 sm:p-6 flex flex-col justify-between space-y-4 backdrop-blur-md">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-[#CEF431]" />
                  Low Stock Monitor
                </h2>
                <p className="text-[11px] text-[#EAF4F4]/60 mt-0.5">
                  SKUs below Reorder Point (ROP)
                </p>
              </div>
              <Link
                to="/inventory"
                className="text-xs font-semibold text-[#CEF431] hover:text-[#bde026] inline-flex items-center gap-1 transition"
              >
                Inspect <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Low stock alerts list */}
            <div className="space-y-2.5 flex-1">
              {isLoading ? (
                <div className="py-12 text-center text-[#EAF4F4]/50 text-xs">Checking safety thresholds...</div>
              ) : metrics.lowStockItems.length === 0 ? (
                <div className="py-10 text-center text-[#EAF4F4]/80 flex flex-col items-center justify-center gap-2">
                  <div className="w-9 h-9 rounded-full bg-[#03D26F]/15 text-[#03D26F] flex items-center justify-center">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-bold text-white">Stock Levels Optimal</p>
                  <p className="text-[11px] text-[#EAF4F4]/60">Every catalog item meets or exceeds safety stock.</p>
                </div>
              ) : (
                metrics.lowStockItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 bg-[#01272e]/80 border border-[#CEF431]/20 rounded-xl flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="min-w-0">
                      <span className="font-mono text-[10px] text-[#CEF431] block font-semibold">
                        {item.product?.sku}
                      </span>
                      <p className="font-semibold text-white truncate">
                        {item.product?.name}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs font-mono font-bold text-[#CEF431] block">
                        {item.available_stock} Avail
                      </span>
                      <span className="text-[10px] font-mono text-[#EAF4F4]/50">
                        ROP: {item.product?.reorder_point}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <Link
              to="/decisions"
              className="w-full py-2.5 px-3 rounded-xl bg-[#03D26F]/15 hover:bg-[#03D26F]/25 border border-[#03D26F]/30 text-center text-xs text-[#03D26F] font-bold transition block"
            >
              Analyze via Decision Agent →
            </Link>
          </div>
        </section>

        {/* Operational Modules Navigation Cards */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#EAF4F4]/60">
              Autonomous Systems & Operational Workflows
            </h2>
            <span className="text-[11px] font-mono text-[#03D26F] flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> All Services Online
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            {/* Decision Agent Card (Featured) */}
            <Link
              to="/decisions"
              className="p-5 rounded-2xl bg-gradient-to-br from-[#01353e] to-[#014651] hover:from-[#014651] hover:to-[#025866] border border-[#03D26F]/30 hover:border-[#03D26F]/60 transition group space-y-2 block shadow-lg shadow-[#03D26F]/5"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-[#03D26F]/20 rounded-xl text-[#03D26F] group-hover:scale-105 transition">
                  <Sparkles className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-[#03D26F] group-hover:translate-x-0.5 transition" />
              </div>
              <div className="flex items-center gap-1.5">
                <h3 className="font-bold text-white text-sm">Decision Agent</h3>
                <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase bg-[#CEF431]/20 text-[#CEF431]">
                  AI Core
                </span>
              </div>
              <p className="text-[#EAF4F4]/70 text-xs leading-relaxed">
                Run 4-agent synthesis & Grok AI reasoning for optimal replenishment and supplier decisions.
              </p>
            </Link>

            {/* Products Card */}
            <Link
              to="/products"
              className="p-5 rounded-2xl bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-[#03D26F]/30 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-[#03D26F]/10 rounded-xl text-[#03D26F] group-hover:scale-105 transition">
                  <Package className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-[#EAF4F4]/40 group-hover:text-[#03D26F] transition" />
              </div>
              <h3 className="font-bold text-white text-sm">Product Registry</h3>
              <p className="text-[#EAF4F4]/70 text-xs leading-relaxed">
                Define master catalog items, SKU identifiers, base unit pricing, and safety reorder points.
              </p>
            </Link>

            {/* Inventory Card */}
            <Link
              to="/inventory"
              className="p-5 rounded-2xl bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-cyan-400/30 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-cyan-500/15 rounded-xl text-cyan-300 group-hover:scale-105 transition">
                  <Boxes className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-[#EAF4F4]/40 group-hover:text-cyan-300 transition" />
              </div>
              <h3 className="font-bold text-white text-sm">Inventory & Stock Levels</h3>
              <p className="text-[#EAF4F4]/70 text-xs leading-relaxed">
                View real-time physical on-hand units, reserved commitments, and derived available stock.
              </p>
            </Link>

            {/* Transactions Card */}
            <Link
              to="/transactions"
              className="p-5 rounded-2xl bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-white/[0.08] hover:border-[#CEF431]/30 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-[#CEF431]/15 rounded-xl text-[#CEF431] group-hover:scale-105 transition">
                  <ArrowRightLeft className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-[#EAF4F4]/40 group-hover:text-[#CEF431] transition" />
              </div>
              <h3 className="font-bold text-white text-sm">Stock Movement Ledger</h3>
              <p className="text-[#EAF4F4]/70 text-xs leading-relaxed">
                Execute verified and immutable Sales, Restocks, Returns, and Adjustments with full audit trails.
              </p>
            </Link>

            {/* Admin User Management Card */}
            {isAdmin && (
              <Link
                to="/users"
                className="p-5 rounded-2xl bg-[#01353e]/60 hover:bg-[#01353e]/90 border border-[#CEF431]/20 hover:border-[#CEF431]/40 transition group space-y-2 block"
              >
                <div className="flex items-center justify-between">
                  <div className="p-2.5 bg-[#CEF431]/15 rounded-xl text-[#CEF431] group-hover:scale-105 transition">
                    <Users className="w-4 h-4" />
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-[#EAF4F4]/40 group-hover:text-[#CEF431] transition" />
                </div>
                <div className="flex items-center gap-1.5">
                  <h3 className="font-bold text-white text-sm">User Management</h3>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold uppercase bg-[#CEF431]/20 text-[#CEF431]">
                    ADMIN
                  </span>
                </div>
                <p className="text-[#EAF4F4]/70 text-xs leading-relaxed">
                  Provision and manage internal Staff and Administrator accounts with RBAC controls.
                </p>
              </Link>
            )}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] py-6 text-center text-xs text-[#EAF4F4]/50 bg-[#01272e] mt-auto">
        SmartSupply AI • Autonomous Inventory Replenishment & Supplier Decision Support System
      </footer>
    </div>
  );
}

