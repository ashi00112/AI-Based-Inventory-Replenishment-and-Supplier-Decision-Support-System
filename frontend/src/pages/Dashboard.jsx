import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 font-mono">
            <TrendingDown className="w-2.5 h-2.5" /> SALE
          </span>
        );
      case 'restock':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 font-mono">
            <TrendingUp className="w-2.5 h-2.5" /> RESTOCK
          </span>
        );
      case 'return':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 font-mono">
            <RotateCcw className="w-2.5 h-2.5" /> RETURN
          </span>
        );
      case 'adjustment':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-mono">
            <Sliders className="w-2.5 h-2.5" /> ADJUST
          </span>
        );
      default:
        return <span className="text-[10px] font-mono text-neutral-500">{type}</span>;
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      <Navbar />

      {/* Main Operational Dashboard Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Welcome Banner */}
        <section className="relative overflow-hidden rounded-2xl bg-neutral-900/50 border border-white/[0.06] p-6 sm:p-8">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="max-w-xl space-y-2">
              <div className="inline-flex items-center gap-2 text-xs font-medium px-2.5 py-1 rounded-full bg-violet-500/10 text-violet-400">
                <Sparkles className="w-3 h-3" />
                Operational Dashboard
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                Welcome back, {user?.name || 'Manager'}
              </h2>
              <p className="text-sm text-neutral-400 leading-relaxed">
                Monitor real-time warehouse stock, track low inventory alerts against reorder thresholds, and execute verified stock movements.
              </p>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 shrink-0">
              <button
                onClick={() => loadDashboardData(true)}
                disabled={isRefreshing}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.06] text-neutral-300 text-xs font-medium transition disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-violet-400' : ''}`} />
                <span>Refresh</span>
              </button>

              <Link
                to="/transactions"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition shadow-lg shadow-violet-600/20 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Record Movement</span>
              </Link>

              <Link
                to="/products"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.06] text-neutral-200 text-xs font-medium transition cursor-pointer"
              >
                <Package className="w-4 h-4 text-violet-400" />
                <span>Add Product</span>
              </Link>
            </div>
          </div>

          {/* Subtle ambient glow */}
          <div className="absolute -right-20 -top-20 w-72 h-72 bg-violet-500/[0.04] rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -left-20 -bottom-20 w-72 h-72 bg-teal-500/[0.03] rounded-full blur-3xl pointer-events-none" />
        </section>

        {/* Live Operational KPI Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Catalog Products */}
          <Link
            to="/products"
            className="group bg-neutral-900/40 hover:bg-neutral-900/60 border border-white/[0.06] hover:border-violet-500/20 rounded-2xl p-5 transition-all flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Catalog Products</span>
              <div className="p-2 rounded-xl bg-violet-500/10 text-violet-400 group-hover:scale-105 transition">
                <Package className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-bold font-mono text-white">
                {isLoading ? '—' : metrics.totalProducts}
              </span>
              <span className="text-[11px] text-violet-400 font-medium inline-flex items-center gap-0.5">
                Manage <ArrowUpRight className="w-3 h-3" />
              </span>
            </div>
          </Link>

          {/* 2. On-Hand Physical Stock */}
          <Link
            to="/inventory"
            className="group bg-neutral-900/40 hover:bg-neutral-900/60 border border-white/[0.06] hover:border-teal-500/20 rounded-2xl p-5 transition-all flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Total On Hand</span>
              <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 group-hover:scale-105 transition">
                <Warehouse className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-bold font-mono text-teal-400">
                {isLoading ? '—' : metrics.totalOnHand.toLocaleString()}
              </span>
              <span className="text-[11px] text-neutral-500 font-medium">units stored</span>
            </div>
          </Link>

          {/* 3. Reserved Orders */}
          <Link
            to="/inventory"
            className="group bg-neutral-900/40 hover:bg-neutral-900/60 border border-white/[0.06] hover:border-blue-500/20 rounded-2xl p-5 transition-all flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Committed / Reserved</span>
              <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 group-hover:scale-105 transition">
                <Boxes className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-bold font-mono text-blue-300">
                {isLoading ? '—' : metrics.totalReserved.toLocaleString()}
              </span>
              <span className="text-[11px] text-neutral-500 font-medium">
                Avail: {metrics.totalAvailable.toLocaleString()}
              </span>
            </div>
          </Link>

          {/* 4. Low Stock Alerts */}
          <Link
            to="/inventory"
            className="group bg-neutral-900/40 hover:bg-neutral-900/60 border border-white/[0.06] hover:border-amber-500/20 rounded-2xl p-5 transition-all flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Reorder Attention</span>
              <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 group-hover:scale-105 transition">
                <AlertTriangle className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-2xl sm:text-3xl font-bold font-mono text-amber-400">
                {isLoading ? '—' : metrics.lowStockCount}
              </span>
              <span className="text-[11px] text-amber-400/70 font-medium">
                {metrics.lowStockCount === 0 ? 'Stock healthy' : 'Below threshold'}
              </span>
            </div>
          </Link>
        </section>

        {/* Core Operational Panels */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Recent Stock Movement Ledger */}
          <div className="lg:col-span-2 bg-neutral-900/40 border border-white/[0.06] rounded-2xl p-5 sm:p-6 flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <ArrowRightLeft className="w-4 h-4 text-violet-400" />
                  Recent Stock Movements
                </h3>
                <p className="text-[11px] text-neutral-500 mt-0.5">
                  Latest immutable inventory transactions
                </p>
              </div>
              <Link
                to="/transactions"
                className="text-xs font-medium text-violet-400 hover:text-violet-300 inline-flex items-center gap-1 transition"
              >
                Full Ledger <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Transaction List */}
            <div className="divide-y divide-white/[0.04]">
              {isLoading ? (
                <div className="py-12 text-center text-neutral-500 flex flex-col items-center gap-2">
                  <Clock className="w-5 h-5 animate-spin text-violet-400" />
                  <span className="text-xs">Loading movements...</span>
                </div>
              ) : recentTransactions.length === 0 ? (
                <div className="py-12 text-center text-neutral-500 flex flex-col items-center gap-2">
                  <ArrowRightLeft className="w-7 h-7 text-neutral-700" />
                  <span className="text-xs">No stock transactions logged yet.</span>
                  <Link
                    to="/transactions"
                    className="text-xs text-violet-400 hover:underline mt-1 font-medium"
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
                        <p className="font-medium text-neutral-200 truncate">
                          {tx.product?.name || `Product #${tx.product_id}`}
                        </p>
                        <p className="text-[10px] text-neutral-500 font-mono">
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
                      <span className="text-[10px] font-mono text-neutral-500">
                        {tx.previous_on_hand} → {tx.new_on_hand}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right Column: Low Stock Threshold Monitor */}
          <div className="bg-neutral-900/40 border border-white/[0.06] rounded-2xl p-5 sm:p-6 flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Low Stock Monitor
                </h3>
                <p className="text-[11px] text-neutral-500 mt-0.5">
                  Items below Reorder Point
                </p>
              </div>
              <Link
                to="/inventory"
                className="text-xs font-medium text-violet-400 hover:text-violet-300 inline-flex items-center gap-1 transition"
              >
                Inspect <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Low stock alerts list */}
            <div className="space-y-2.5 flex-1">
              {isLoading ? (
                <div className="py-12 text-center text-neutral-500 text-xs">Checking stock...</div>
              ) : metrics.lowStockItems.length === 0 ? (
                <div className="py-10 text-center text-neutral-400 flex flex-col items-center justify-center gap-2">
                  <div className="w-9 h-9 rounded-full bg-teal-500/10 text-teal-400 flex items-center justify-center">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-medium text-neutral-300">All Stock Levels Optimal</p>
                  <p className="text-[11px] text-neutral-500">Every catalog item meets safety thresholds.</p>
                </div>
              ) : (
                metrics.lowStockItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 bg-neutral-950/60 border border-amber-500/10 rounded-xl flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="min-w-0">
                      <span className="font-mono text-[10px] text-amber-400 block font-semibold">
                        {item.product?.sku}
                      </span>
                      <p className="font-medium text-neutral-200 truncate">
                        {item.product?.name}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs font-mono font-bold text-amber-400 block">
                        {item.available_stock} Avail
                      </span>
                      <span className="text-[10px] font-mono text-neutral-500">
                        ROP: {item.product?.reorder_point}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <Link
              to="/transactions"
              className="w-full py-2 px-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.06] text-center text-xs text-neutral-300 hover:text-white font-medium transition block"
            >
              Restock via Transactions →
            </Link>
          </div>
        </section>

        {/* Operational Modules Navigation Cards */}
        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
            System Modules & Workflows
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            {/* Decision Agent Card */}
            <Link
              to="/decisions"
              className="p-5 rounded-2xl bg-neutral-900/30 hover:bg-neutral-900/50 border border-violet-500/20 hover:border-violet-500/40 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-violet-500/10 rounded-xl text-violet-400 group-hover:scale-105 transition">
                  <Sparkles className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-neutral-600 group-hover:text-violet-400 transition" />
              </div>
              <h4 className="font-semibold text-white text-sm">Decision Agent</h4>
              <p className="text-neutral-500 text-xs leading-relaxed">
                Run multi-agent synthesis & Grok AI reasoning for optimal replenishment and supplier decisions.
              </p>
            </Link>

            {/* Products Card */}
            <Link
              to="/products"
              className="p-5 rounded-2xl bg-neutral-900/30 hover:bg-neutral-900/50 border border-white/[0.06] hover:border-violet-500/20 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-violet-500/10 rounded-xl text-violet-400 group-hover:scale-105 transition">
                  <Package className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-neutral-600 group-hover:text-violet-400 transition" />
              </div>
              <h4 className="font-semibold text-white text-sm">Product Registry</h4>
              <p className="text-neutral-500 text-xs leading-relaxed">
                Define master catalog items, SKU identifiers, base unit pricing, and safety reorder points.
              </p>
            </Link>

            {/* Inventory Card */}
            <Link
              to="/inventory"
              className="p-5 rounded-2xl bg-neutral-900/30 hover:bg-neutral-900/50 border border-white/[0.06] hover:border-teal-500/20 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-teal-500/10 rounded-xl text-teal-400 group-hover:scale-105 transition">
                  <Boxes className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-neutral-600 group-hover:text-teal-400 transition" />
              </div>
              <h4 className="font-semibold text-white text-sm">Inventory & Stock Levels</h4>
              <p className="text-neutral-500 text-xs leading-relaxed">
                View real-time physical on-hand units, reserved commitments, and derived available stock.
              </p>
            </Link>

            {/* Transactions Card */}
            <Link
              to="/transactions"
              className="p-5 rounded-2xl bg-neutral-900/30 hover:bg-neutral-900/50 border border-white/[0.06] hover:border-blue-500/20 transition group space-y-2 block"
            >
              <div className="flex items-center justify-between">
                <div className="p-2.5 bg-blue-500/10 rounded-xl text-blue-400 group-hover:scale-105 transition">
                  <ArrowRightLeft className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-neutral-600 group-hover:text-blue-400 transition" />
              </div>
              <h4 className="font-semibold text-white text-sm">Stock Movement Ledger</h4>
              <p className="text-neutral-500 text-xs leading-relaxed">
                Execute verified and immutable Sales, Restocks, Returns, and Adjustments with full audit trails.
              </p>
            </Link>

            {/* Admin User Management Card */}
            {isAdmin && (
              <Link
                to="/users"
                className="p-5 rounded-2xl bg-neutral-900/30 hover:bg-neutral-900/50 border border-violet-500/20 hover:border-violet-500/40 transition group space-y-2 block"
              >
                <div className="flex items-center justify-between">
                  <div className="p-2.5 bg-violet-500/10 rounded-xl text-violet-400 group-hover:scale-105 transition">
                    <Users className="w-4 h-4" />
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-neutral-600 group-hover:text-violet-400 transition" />
                </div>
                <h4 className="font-semibold text-white text-sm">User Management</h4>
                <p className="text-neutral-500 text-xs leading-relaxed">
                  Provision and manage internal Staff and Administrator accounts with RBAC controls.
                </p>
              </Link>
            )}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.04] py-6 text-center text-xs text-neutral-600 mt-auto">
        SmartSupply • AI-Based Inventory Replenishment & Supplier Decision Support System
      </footer>
    </div>
  );
}
