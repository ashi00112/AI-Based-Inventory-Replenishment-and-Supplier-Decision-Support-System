import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Package,
  Boxes,
  Pencil,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  X,
  Search,
  TrendingDown,
  Warehouse,
  ArrowRightLeft,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getInventory, updateProductInventory } from '../services/inventoryApi';
import Navbar from '../components/Navbar';

export default function Inventory() {
  const { user } = useAuth();

  // Inventory Table State
  const [inventoryList, setInventoryList] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [serverError, setServerError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Edit Stock Modal State
  const [editingItem, setEditingItem] = useState(null); // Inventory item currently being edited
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formData, setFormData] = useState({
    on_hand: '0',
    reserved: '0',
    incoming: '0',
  });
  const [fieldErrors, setFieldErrors] = useState({});

  // Fetch Inventory List
  const fetchInventoryData = useCallback(async () => {
    setIsLoading(true);
    setServerError('');
    const result = await getInventory();
    if (result.success) {
      setInventoryList(result.data);
    } else {
      setServerError(result.error);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchInventoryData();
  }, [fetchInventoryData]);

  // Auto-dismiss success notification
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Open Edit Modal
  const handleOpenEditModal = (item) => {
    setEditingItem(item);
    setFormData({
      on_hand: String(item.on_hand ?? 0),
      reserved: String(item.reserved ?? 0),
      incoming: String(item.incoming ?? 0),
    });
    setFieldErrors({});
    setFormError('');
  };

  const handleCloseEditModal = () => {
    setEditingItem(null);
    setFormError('');
    setFieldErrors({});
  };

  // Form Field Change Handler
  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: '' }));
    }
    if (formError) setFormError('');
  };

  // Derived available stock in the edit modal
  const modalAvailableStock = useMemo(() => {
    const onHand = parseInt(formData.on_hand, 10);
    const reserved = parseInt(formData.reserved, 10);
    if (isNaN(onHand) || isNaN(reserved)) return 0;
    return onHand - reserved;
  }, [formData.on_hand, formData.reserved]);

  // Client-side Validation
  const validateForm = () => {
    const errors = {};
    const onHand = parseInt(formData.on_hand, 10);
    const reserved = parseInt(formData.reserved, 10);
    const incoming = parseInt(formData.incoming, 10);

    if (formData.on_hand === '' || isNaN(onHand)) {
      errors.on_hand = 'On Hand quantity is required.';
    } else if (onHand < 0) {
      errors.on_hand = 'On Hand cannot be negative.';
    }

    if (formData.reserved === '' || isNaN(reserved)) {
      errors.reserved = 'Reserved quantity is required.';
    } else if (reserved < 0) {
      errors.reserved = 'Reserved cannot be negative.';
    }

    if (formData.incoming === '' || isNaN(incoming)) {
      errors.incoming = 'Incoming quantity is required.';
    } else if (incoming < 0) {
      errors.incoming = 'Incoming cannot be negative.';
    }

    if (!errors.on_hand && !errors.reserved && reserved > onHand) {
      errors.reserved = `Reserved stock (${reserved}) cannot exceed on-hand stock (${onHand}).`;
    }

    return errors;
  };

  // Form Submit Handler
  const handleFormSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting || !editingItem) return;

    setFormError('');
    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);
    const result = await updateProductInventory(editingItem.product_id, {
      on_hand: parseInt(formData.on_hand, 10),
      reserved: parseInt(formData.reserved, 10),
      incoming: parseInt(formData.incoming, 10),
    });
    setIsSubmitting(false);

    if (result.success) {
      const productName = editingItem.product?.name || `Product #${editingItem.product_id}`;
      setSuccessMessage(`Inventory stock updated successfully for '${productName}'.`);
      handleCloseEditModal();
      fetchInventoryData();
    } else {
      setFormError(result.error);
    }
  };

  // Filtered Inventory List
  const filteredList = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return inventoryList;
    return inventoryList.filter((item) => {
      const sku = item.product?.sku?.toLowerCase() || '';
      const name = item.product?.name?.toLowerCase() || '';
      return sku.includes(query) || name.includes(query);
    });
  }, [inventoryList, searchQuery]);

  // Operational Metrics
  const summaryMetrics = useMemo(() => {
    const totalProducts = inventoryList.length;
    let lowStockCount = 0;
    let totalOnHandUnits = 0;

    for (const item of inventoryList) {
      totalOnHandUnits += item.on_hand || 0;
      const rop = item.product?.reorder_point ?? 0;
      if (item.available_stock <= rop) {
        lowStockCount += 1;
      }
    }

    return { totalProducts, lowStockCount, totalOnHandUnits };
  }, [inventoryList]);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      <Navbar />

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Breadcrumb Navigation & Record Movement Action */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-neutral-500 font-medium">
            <Link to="/" className="hover:text-violet-400 transition">Dashboard</Link>
            <span>/</span>
            <span className="text-neutral-200">Inventory</span>
          </div>

          <Link
            to="/transactions"
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-violet-500/10 hover:bg-violet-500/15 text-violet-400 font-medium text-xs transition cursor-pointer self-start sm:self-auto"
          >
            <ArrowRightLeft className="w-3.5 h-3.5" />
            <span>Record Movement / Transaction</span>
          </Link>
        </div>

        {/* Global Feedback Notifications */}
        {serverError && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{serverError}</span>
            </div>
            <button
              onClick={() => setServerError('')}
              className="p-1 hover:bg-red-500/20 rounded text-red-400"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="p-4 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
              <span>{successMessage}</span>
            </div>
            <button
              onClick={() => setSuccessMessage('')}
              className="p-1 hover:bg-teal-500/20 rounded text-teal-400"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Operational Stock Summary Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-neutral-900/40 border border-white/[0.06] rounded-xl p-4 flex items-center gap-4">
            <div className="p-3 bg-violet-500/10 rounded-lg text-violet-400">
              <Boxes className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-neutral-500 font-medium">Tracked Products</p>
              <p className="text-xl font-bold text-white mt-0.5">{summaryMetrics.totalProducts}</p>
            </div>
          </div>

          <div className="bg-neutral-900/40 border border-white/[0.06] rounded-xl p-4 flex items-center gap-4">
            <div className="p-3 bg-amber-500/10 rounded-lg text-amber-400">
              <TrendingDown className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-neutral-500 font-medium">Low Stock Products</p>
              <p className="text-xl font-bold text-amber-400 mt-0.5">{summaryMetrics.lowStockCount}</p>
            </div>
          </div>

          <div className="bg-neutral-900/40 border border-white/[0.06] rounded-xl p-4 flex items-center gap-4">
            <div className="p-3 bg-teal-500/10 rounded-lg text-teal-400">
              <Warehouse className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-neutral-500 font-medium">Total On-Hand Units</p>
              <p className="text-xl font-bold text-white mt-0.5">{summaryMetrics.totalOnHandUnits.toLocaleString()}</p>
            </div>
          </div>
        </section>

        {/* Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-neutral-900/30 p-3 rounded-xl border border-white/[0.06]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-neutral-600 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by SKU or Product name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-neutral-950 border border-white/[0.06] rounded-lg text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-violet-500/40 transition"
            />
          </div>
          <span className="text-xs text-neutral-500 font-medium px-2 text-right">
            Showing {filteredList.length} of {inventoryList.length} items
          </span>
        </div>

        {/* Inventory Stock Table */}
        <section className="bg-neutral-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/[0.06] bg-neutral-900/60 text-neutral-500 font-medium uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4">SKU</th>
                  <th className="py-3 px-4">Product</th>
                  <th className="py-3 px-4 text-right">On Hand</th>
                  <th className="py-3 px-4 text-right">Reserved</th>
                  <th className="py-3 px-4 text-right">Available</th>
                  <th className="py-3 px-4 text-right">Incoming</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {isLoading ? (
                  <tr>
                    <td colSpan="8" className="py-12 text-center text-neutral-500">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
                        <span className="text-xs">Loading current inventory levels...</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredList.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="py-12 text-center text-neutral-500">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Boxes className="w-8 h-8 text-neutral-700" />
                        <span className="text-xs">
                          {searchQuery ? 'No stock records match your query.' : 'No products found in the catalog.'}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredList.map((item) => {
                    const rop = item.product?.reorder_point ?? 0;
                    const isLowStock = item.available_stock <= rop;

                    return (
                      <tr key={item.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="py-3.5 px-4 font-mono font-medium text-violet-400">
                          {item.product?.sku || 'N/A'}
                        </td>
                        <td className="py-3.5 px-4 font-medium text-neutral-100">
                          <div>{item.product?.name || `Product #${item.product_id}`}</div>
                          <div className="text-[10px] text-neutral-600 font-mono">
                            ROP Threshold: {rop} units
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-neutral-200">
                          {item.on_hand}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-neutral-500">
                          {item.reserved}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-white">
                          {item.available_stock}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-blue-300">
                          +{item.incoming}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {isLowStock ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-mono">
                              <AlertTriangle className="w-3 h-3" />
                              LOW STOCK
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 font-mono">
                              <CheckCircle2 className="w-3 h-3" />
                              IN STOCK
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              to={`/transactions?newForProduct=${item.product_id}`}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-violet-500/10 hover:bg-violet-500/15 text-violet-400 hover:text-violet-300 font-medium transition cursor-pointer text-xs"
                              title="Record stock movement transaction"
                            >
                              <ArrowRightLeft className="w-3 h-3" />
                              <span>Transact</span>
                            </Link>
                            <button
                              type="button"
                              onClick={() => handleOpenEditModal(item)}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.07] text-neutral-400 hover:text-white font-medium transition cursor-pointer text-xs"
                              title="Direct edit stock values"
                            >
                              <Pencil className="w-3 h-3" />
                              <span>Edit</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {/* Edit Stock Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-white/[0.08] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <div>
                <h3 className="text-base font-semibold text-white">
                  Update Stock Levels
                </h3>
                <p className="text-xs text-violet-400 font-mono mt-0.5">
                  {editingItem.product?.sku} — {editingItem.product?.name}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseEditModal}
                className="p-1 text-neutral-500 hover:text-white rounded-lg hover:bg-white/[0.06] transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleFormSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                {/* On Hand */}
                <div>
                  <label className="block text-neutral-400 font-medium mb-1">
                    On Hand Units <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="number"
                    name="on_hand"
                    min="0"
                    step="1"
                    value={formData.on_hand}
                    onChange={handleFormChange}
                    className={`w-full px-3 py-2 bg-neutral-950 border rounded-lg text-neutral-100 focus:outline-none transition ${
                      fieldErrors.on_hand
                        ? 'border-red-500 focus:border-red-500'
                        : 'border-white/[0.08] focus:border-violet-500'
                    }`}
                  />
                  {fieldErrors.on_hand && (
                    <p className="text-[11px] text-red-400 mt-1">{fieldErrors.on_hand}</p>
                  )}
                  <p className="text-[10px] text-neutral-600 mt-1">Physical stock present in warehouse</p>
                </div>

                {/* Reserved */}
                <div>
                  <label className="block text-neutral-400 font-medium mb-1">
                    Reserved Units <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="number"
                    name="reserved"
                    min="0"
                    step="1"
                    value={formData.reserved}
                    onChange={handleFormChange}
                    className={`w-full px-3 py-2 bg-neutral-950 border rounded-lg text-neutral-100 focus:outline-none transition ${
                      fieldErrors.reserved
                        ? 'border-red-500 focus:border-red-500'
                        : 'border-white/[0.08] focus:border-violet-500'
                    }`}
                  />
                  {fieldErrors.reserved && (
                    <p className="text-[11px] text-red-400 mt-1">{fieldErrors.reserved}</p>
                  )}
                  <p className="text-[10px] text-neutral-600 mt-1">Committed orders (≤ On Hand)</p>
                </div>
              </div>

              {/* Read-Only Derived Available Stock */}
              <div className="p-3 bg-neutral-950/70 border border-white/[0.06] rounded-lg flex items-center justify-between">
                <div>
                  <span className="text-neutral-400 font-medium block">Derived Available Stock</span>
                  <span className="text-[10px] text-neutral-600 font-mono">
                    Formula: On Hand ({formData.on_hand || 0}) - Reserved ({formData.reserved || 0})
                  </span>
                </div>
                <div className={`font-mono text-base font-bold ${modalAvailableStock < 0 ? 'text-red-400' : 'text-teal-400'}`}>
                  {modalAvailableStock}
                </div>
              </div>

              {/* Incoming */}
              <div>
                <label className="block text-neutral-400 font-medium mb-1">
                  Incoming Units (from Suppliers) <span className="text-violet-400">*</span>
                </label>
                <input
                  type="number"
                  name="incoming"
                  min="0"
                  step="1"
                  value={formData.incoming}
                  onChange={handleFormChange}
                  className={`w-full px-3 py-2 bg-neutral-950 border rounded-lg text-neutral-100 focus:outline-none transition ${
                    fieldErrors.incoming
                      ? 'border-red-500 focus:border-red-500'
                      : 'border-white/[0.08] focus:border-violet-500'
                  }`}
                />
                {fieldErrors.incoming && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.incoming}</p>
                )}
                <p className="text-[10px] text-neutral-600 mt-1">Units in transit from purchase orders</p>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={handleCloseEditModal}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.07] text-neutral-300 font-medium transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-semibold transition shadow-sm shadow-violet-600/20 disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Stock Levels</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-white/[0.04] py-6 text-center text-xs text-neutral-600 mt-auto">
        AI-Based Inventory Replenishment and Supplier Decision Support System • Operational Inventory Module
      </footer>
    </div>
  );
}
