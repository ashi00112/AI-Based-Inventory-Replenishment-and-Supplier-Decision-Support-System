import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRightLeft,
  Plus,
  Search,
  Filter,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  TrendingDown,
  TrendingUp,
  RotateCcw,
  Sliders,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getInventory } from '../services/inventoryApi';
import {
  createInventoryTransaction,
  getInventoryTransactions,
} from '../services/inventoryTransactionApi';
import Navbar from '../components/Navbar';

export default function Transactions() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Transactions State
  const [transactions, setTransactions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [serverError, setServerError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Products/Inventory Registry (for selector and stock preview)
  const [inventoryMap, setInventoryMap] = useState({});
  const [inventoryList, setInventoryList] = useState([]);

  // Filtering State
  const [selectedProductFilter, setSelectedProductFilter] = useState(
    searchParams.get('productId') || ''
  );
  const [selectedTypeFilter, setSelectedTypeFilter] = useState(
    searchParams.get('type') || ''
  );
  const [searchQuery, setSearchQuery] = useState('');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formData, setFormData] = useState({
    product_id: '',
    transaction_type: 'sale',
    quantity: '',
    note: '',
  });
  const [fieldErrors, setFieldErrors] = useState({});

  // Fetch Inventory and Products
  const loadInventory = useCallback(async () => {
    const res = await getInventory({ limit: 500 });
    if (res.success) {
      setInventoryList(res.data);
      const map = {};
      for (const item of res.data) {
        map[item.product_id] = item;
      }
      setInventoryMap(map);
    }
  }, []);

  // Fetch Transactions List
  const fetchTransactions = useCallback(async () => {
    setIsLoading(true);
    setServerError('');
    const filters = {};
    if (selectedProductFilter) filters.product_id = parseInt(selectedProductFilter, 10);
    if (selectedTypeFilter) filters.transaction_type = selectedTypeFilter;

    const res = await getInventoryTransactions(filters);
    if (res.success) {
      setTransactions(res.data);
    } else {
      setServerError(res.error);
    }
    setIsLoading(false);
  }, [selectedProductFilter, selectedTypeFilter]);

  useEffect(() => {
    loadInventory();
  }, [loadInventory]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  // Open modal if URL query param 'new' is present
  useEffect(() => {
    const preselectedProduct = searchParams.get('newForProduct');
    if (preselectedProduct) {
      handleOpenModal(preselectedProduct);
    }
  }, [searchParams]);

  // Auto-dismiss success notification
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Open Record Modal
  const handleOpenModal = (productId = '') => {
    setFormData({
      product_id: productId || (inventoryList[0]?.product_id ? String(inventoryList[0].product_id) : ''),
      transaction_type: 'sale',
      quantity: '',
      note: '',
    });
    setFieldErrors({});
    setFormError('');
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setFormError('');
    setFieldErrors({});
    // Clean query param if present
    if (searchParams.get('newForProduct')) {
      searchParams.delete('newForProduct');
      setSearchParams(searchParams);
    }
  };

  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: '' }));
    }
    if (formError) setFormError('');
  };

  // Currently selected product in modal
  const selectedProductInventory = useMemo(() => {
    if (!formData.product_id) return null;
    return inventoryMap[parseInt(formData.product_id, 10)] || null;
  }, [formData.product_id, inventoryMap]);

  // Client Validation
  const validateForm = () => {
    const errors = {};
    if (!formData.product_id) {
      errors.product_id = 'Please select a product.';
    }

    const qty = parseInt(formData.quantity, 10);
    if (formData.quantity === '' || isNaN(qty)) {
      errors.quantity = 'Quantity is required.';
    } else if (formData.transaction_type === 'adjustment') {
      if (qty === 0) {
        errors.quantity = 'Adjustment quantity cannot be 0.';
      } else if (selectedProductInventory) {
        const prospective = selectedProductInventory.on_hand + qty;
        if (prospective < 0) {
          errors.quantity = `Adjustment of ${qty} would reduce on-hand stock below 0 (Current: ${selectedProductInventory.on_hand}).`;
        } else if (prospective < selectedProductInventory.reserved) {
          errors.quantity = `Adjustment of ${qty} would reduce on-hand stock below reserved stock (${selectedProductInventory.reserved}).`;
        }
      }
    } else {
      if (qty <= 0) {
        errors.quantity = 'Quantity must be greater than 0.';
      } else if (formData.transaction_type === 'sale' && selectedProductInventory) {
        const available = selectedProductInventory.available_stock;
        if (qty > available) {
          errors.quantity = `Insufficient available stock for this sale. Available: ${available} (On Hand: ${selectedProductInventory.on_hand}, Reserved: ${selectedProductInventory.reserved}).`;
        }
      }
    }

    return errors;
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setFormError('');
    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);
    const result = await createInventoryTransaction({
      product_id: parseInt(formData.product_id, 10),
      transaction_type: formData.transaction_type,
      quantity: parseInt(formData.quantity, 10),
      note: formData.note,
    });
    setIsSubmitting(false);

    if (result.success) {
      const typeLabel = formData.transaction_type.toUpperCase();
      setSuccessMessage(
        `Recorded ${typeLabel} of ${formData.quantity} units for product SKU '${result.data.product?.sku}'.`
      );
      handleCloseModal();
      fetchTransactions();
      loadInventory(); // Refresh stock map
    } else {
      setFormError(result.error);
    }
  };

  // Filtered Transactions
  const filteredTransactions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return transactions;
    return transactions.filter((tx) => {
      const sku = tx.product?.sku?.toLowerCase() || '';
      const name = tx.product?.name?.toLowerCase() || '';
      const note = tx.note?.toLowerCase() || '';
      return sku.includes(q) || name.includes(q) || note.includes(q);
    });
  }, [transactions, searchQuery]);

  // Helper badge for transaction type
  const renderTypeBadge = (type) => {
    switch (type) {
      case 'sale':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-teal-500/15 text-teal-300 border border-teal-500/30 font-mono">
            <TrendingDown className="w-3 h-3" />
            SALE
          </span>
        );
      case 'restock':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-malachite/15 text-malachite border border-malachite/30 font-mono">
            <TrendingUp className="w-3 h-3" />
            RESTOCK
          </span>
        );
      case 'return':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-starship/15 text-starship border border-starship/30 font-mono">
            <RotateCcw className="w-3 h-3" />
            RETURN
          </span>
        );
      case 'adjustment':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-amber-400/15 text-amber-300 border border-amber-400/30 font-mono">
            <Sliders className="w-3 h-3" />
            ADJUSTMENT
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-[#EAF4F4]/50">
            {type?.toUpperCase()}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col">
      <Navbar />

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Breadcrumb & Action */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-[#EAF4F4]/60 font-medium">
            <Link to="/" className="hover:text-malachite transition">Dashboard</Link>
            <span>/</span>
            <Link to="/inventory" className="hover:text-malachite transition">Inventory</Link>
            <span>/</span>
            <span className="text-white font-semibold">Transactions Ledger</span>
          </div>

          <button
            type="button"
            onClick={() => handleOpenModal()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-malachite hover:bg-[#03b860] text-[#161514] font-bold rounded-xl text-xs transition shadow-lg shadow-malachite/20 cursor-pointer self-start sm:self-auto shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Record Transaction</span>
          </button>
        </div>

        {/* Global Notifications */}
        {serverError && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/25 text-red-200 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{serverError}</span>
            </div>
            <button onClick={() => setServerError('')} className="p-1 hover:bg-red-500/20 rounded text-red-400">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="p-4 rounded-xl bg-malachite/15 border border-malachite/30 text-malachite text-xs flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-malachite shrink-0" />
              <span>{successMessage}</span>
            </div>
            <button onClick={() => setSuccessMessage('')} className="p-1 hover:bg-malachite/20 rounded text-malachite">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Filter Bar */}
        <section className="bg-[#01353e] p-4 rounded-2xl border border-white/[0.08] shadow-lg flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 text-xs">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 text-[#EAF4F4]/40 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by SKU, product name, or note..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-[#01272e] border border-white/[0.08] rounded-xl text-xs text-[#EAF4F4] placeholder-[#EAF4F4]/40 focus:outline-none focus:border-malachite transition"
            />
          </div>

          <div className="flex items-center gap-3">
            {/* Filter by Product */}
            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-[#EAF4F4]/50 shrink-0" />
              <select
                value={selectedProductFilter}
                onChange={(e) => setSelectedProductFilter(e.target.value)}
                className="px-3 py-2 bg-[#01272e] border border-white/[0.08] rounded-xl text-[#EAF4F4] focus:outline-none focus:border-malachite"
              >
                <option value="">All Products</option>
                {inventoryList.map((item) => (
                  <option key={item.product_id} value={item.product_id}>
                    {item.product?.sku} — {item.product?.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Filter by Type */}
            <select
              value={selectedTypeFilter}
              onChange={(e) => setSelectedTypeFilter(e.target.value)}
              className="px-3 py-2 bg-[#01272e] border border-white/[0.08] rounded-xl text-[#EAF4F4] focus:outline-none focus:border-malachite"
            >
              <option value="">All Types</option>
              <option value="sale">Sale</option>
              <option value="restock">Restock</option>
              <option value="return">Return</option>
              <option value="adjustment">Adjustment</option>
            </select>
          </div>
        </section>

        {/* Transaction History Table */}
        <section className="bg-[#01353e] border border-white/[0.08] rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/[0.08] bg-[#01272e]/90 text-[#EAF4F4]/60 font-semibold uppercase tracking-wider text-[10px]">
                  <th className="py-3.5 px-4">Date / Time</th>
                  <th className="py-3.5 px-4">Product SKU</th>
                  <th className="py-3.5 px-4">Product Name</th>
                  <th className="py-3.5 px-4 text-center">Type</th>
                  <th className="py-3.5 px-4 text-right">Quantity</th>
                  <th className="py-3.5 px-4 text-right">Previous Stock</th>
                  <th className="py-3.5 px-4 text-right">New Stock</th>
                  <th className="py-3.5 px-4">Note / Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {isLoading ? (
                  <tr>
                    <td colSpan="8" className="py-12 text-center text-[#EAF4F4]/50">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 className="w-6 h-6 animate-spin text-malachite" />
                        <span className="text-xs">Loading transaction history...</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredTransactions.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="py-12 text-center text-[#EAF4F4]/50">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <ArrowRightLeft className="w-8 h-8 text-[#EAF4F4]/30" />
                        <span className="text-xs">
                          {searchQuery || selectedProductFilter || selectedTypeFilter
                            ? 'No transactions match the selected filters.'
                            : 'No inventory transactions recorded yet. Click "Record Transaction" to record stock movement.'}
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredTransactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-white/[0.03] transition-colors">
                      <td className="py-3.5 px-4 font-mono text-[#EAF4F4]/50 whitespace-nowrap">
                        {new Date(tx.created_at).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-malachite">
                        {tx.product?.sku || 'N/A'}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-white">
                        {tx.product?.name || `Product #${tx.product_id}`}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {renderTypeBadge(tx.transaction_type)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-white">
                        {tx.transaction_type === 'sale'
                          ? `-${tx.quantity}`
                          : tx.transaction_type === 'adjustment' && tx.quantity > 0
                          ? `+${tx.quantity}`
                          : tx.quantity > 0
                          ? `+${tx.quantity}`
                          : tx.quantity}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono text-[#EAF4F4]/50">
                        {tx.previous_on_hand}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-semibold text-white">
                        {tx.new_on_hand}
                      </td>
                      <td className="py-3.5 px-4 text-[#EAF4F4]/60 max-w-xs truncate">
                        {tx.note || <span className="text-[#EAF4F4]/30 italic">—</span>}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {/* Record Transaction Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#01272e]/85 backdrop-blur-md">
          <div className="bg-[#01353e] border border-white/[0.1] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <ArrowRightLeft className="w-4 h-4 text-malachite" />
                  Record Stock Movement
                </h3>
                <p className="text-xs text-[#EAF4F4]/60 mt-0.5">
                  Update inventory levels via an immutable transaction event.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseModal}
                className="p-1 text-[#EAF4F4]/60 hover:text-white rounded-lg hover:bg-white/[0.08] transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-500/10 border border-red-500/25 rounded-xl text-red-200 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleFormSubmit} className="space-y-4 text-xs">
              {/* Product Selector */}
              <div>
                <label className="block text-[#EAF4F4]/80 font-medium mb-1">
                  Product <span className="text-malachite">*</span>
                </label>
                <select
                  name="product_id"
                  value={formData.product_id}
                  onChange={handleFormChange}
                  className={`w-full px-3 py-2 bg-[#01272e] border rounded-xl text-white focus:outline-none transition ${
                    fieldErrors.product_id ? 'border-red-500' : 'border-white/[0.1] focus:border-malachite'
                  }`}
                >
                  <option value="">Select a product...</option>
                  {inventoryList.map((item) => (
                    <option key={item.product_id} value={item.product_id}>
                      {item.product?.sku} — {item.product?.name}
                    </option>
                  ))}
                </select>
                {fieldErrors.product_id && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.product_id}</p>
                )}
              </div>

              {/* Current Stock Preview Card */}
              {selectedProductInventory && (
                <div className="p-3.5 bg-[#01272e]/90 border border-white/[0.08] rounded-xl grid grid-cols-3 text-center gap-2 font-mono">
                  <div>
                    <span className="text-[10px] text-[#EAF4F4]/50 block uppercase">On Hand</span>
                    <span className="text-sm font-bold text-white">
                      {selectedProductInventory.on_hand}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#EAF4F4]/50 block uppercase">Reserved</span>
                    <span className="text-sm font-bold text-[#EAF4F4]/60">
                      {selectedProductInventory.reserved}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#EAF4F4]/50 block uppercase">Available</span>
                    <span className="text-sm font-bold text-malachite">
                      {selectedProductInventory.available_stock}
                    </span>
                  </div>
                </div>
              )}

              {/* Transaction Type */}
              <div>
                <label className="block text-[#EAF4F4]/80 font-medium mb-1">
                  Transaction Type <span className="text-malachite">*</span>
                </label>
                <select
                  name="transaction_type"
                  value={formData.transaction_type}
                  onChange={handleFormChange}
                  className="w-full px-3 py-2 bg-[#01272e] border border-white/[0.1] rounded-xl text-white focus:outline-none focus:border-malachite"
                >
                  <option value="sale">Sale (Reduces On Hand, cannot exceed Available)</option>
                  <option value="restock">Restock (Increases On Hand)</option>
                  <option value="return">Return (Increases On Hand)</option>
                  <option value="adjustment">Adjustment (Correction delta: + or -)</option>
                </select>
              </div>

              {/* Quantity */}
              <div>
                <label className="block text-[#EAF4F4]/80 font-medium mb-1">
                  Quantity <span className="text-malachite">*</span>
                </label>
                <input
                  type="number"
                  name="quantity"
                  step="1"
                  placeholder={
                    formData.transaction_type === 'adjustment'
                      ? 'e.g. +10 or -5'
                      : 'e.g. 25'
                  }
                  value={formData.quantity}
                  onChange={handleFormChange}
                  className={`w-full px-3 py-2 bg-[#01272e] border rounded-xl text-white focus:outline-none transition ${
                    fieldErrors.quantity ? 'border-red-500' : 'border-white/[0.1] focus:border-malachite'
                  }`}
                />
                {fieldErrors.quantity && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.quantity}</p>
                )}
                <p className="text-[10px] text-[#EAF4F4]/50 mt-1">
                  {formData.transaction_type === 'adjustment'
                    ? 'Enter positive number to increase stock, negative to decrease.'
                    : 'Must be a positive integer.'}
                </p>
              </div>

              {/* Note / Reference */}
              <div>
                <label className="block text-[#EAF4F4]/80 font-medium mb-1">
                  Note / Reference (Optional)
                </label>
                <input
                  type="text"
                  name="note"
                  maxLength={500}
                  placeholder="e.g. Invoice #8842, Supplier PO-12, RMA-301..."
                  value={formData.note}
                  onChange={handleFormChange}
                  className="w-full px-3 py-2 bg-[#01272e] border border-white/[0.1] rounded-xl text-white focus:outline-none focus:border-malachite"
                />
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-[#EAF4F4]/80 font-medium transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-malachite hover:bg-[#03b860] text-[#161514] font-bold transition shadow-lg shadow-malachite/20 disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-[#161514]" />
                      <span>Recording...</span>
                    </>
                  ) : (
                    <span>Commit Transaction</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-6 text-center text-xs text-[#EAF4F4]/40 mt-auto">
        AI-Based Inventory Replenishment and Supplier Decision Support System • Inventory Transactions Ledger
      </footer>
    </div>
  );
}
