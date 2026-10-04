import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Package,
  Plus,
  Pencil,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  Search,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getProducts,
  createProduct,
  updateProduct,
  deleteProduct,
} from '../services/productApi';
import Navbar from '../components/Navbar';

export default function Products() {
  const { user } = useAuth();

  // Catalog State
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [serverError, setServerError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Modal State
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null); // null = create mode
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Form Fields
  const [formData, setFormData] = useState({
    sku: '',
    name: '',
    category: '',
    description: '',
    unit_price: '',
    reorder_point: '0',
    is_active: true,
  });
  const [fieldErrors, setFieldErrors] = useState({});

  // Delete Confirmation State
  const [deletingProduct, setDeletingProduct] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const fetchProductList = useCallback(async () => {
    setIsLoading(true);
    setServerError('');
    const result = await getProducts();
    if (result.success) {
      setProducts(result.data);
    } else {
      setServerError(result.error);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchProductList();
  }, [fetchProductList]);

  // Dismiss feedback messages automatically after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Open Create Modal
  const handleOpenCreateModal = () => {
    setEditingProduct(null);
    setFormData({
      sku: '',
      name: '',
      category: '',
      description: '',
      unit_price: '',
      reorder_point: '0',
      is_active: true,
    });
    setFieldErrors({});
    setFormError('');
    setIsFormModalOpen(true);
  };

  // Open Edit Modal
  const handleOpenEditModal = (product) => {
    setEditingProduct(product);
    setFormData({
      sku: product.sku || '',
      name: product.name || '',
      category: product.category || '',
      description: product.description || '',
      unit_price: product.unit_price ? String(product.unit_price) : '0.00',
      reorder_point: product.reorder_point !== undefined ? String(product.reorder_point) : '0',
      is_active: Boolean(product.is_active),
    });
    setFieldErrors({});
    setFormError('');
    setIsFormModalOpen(true);
  };

  const handleFormChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));

    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: '' }));
    }
    if (formError) setFormError('');
  };

  const validateForm = () => {
    const errors = {};
    if (!formData.sku.trim()) {
      errors.sku = 'SKU is required.';
    } else if (formData.sku.trim().length > 50) {
      errors.sku = 'SKU must not exceed 50 characters.';
    }

    if (!formData.name.trim()) {
      errors.name = 'Product name is required.';
    } else if (formData.name.trim().length > 200) {
      errors.name = 'Product name must not exceed 200 characters.';
    }

    const price = parseFloat(formData.unit_price);
    if (formData.unit_price === '' || isNaN(price)) {
      errors.unit_price = 'Unit price is required.';
    } else if (price < 0) {
      errors.unit_price = 'Unit price cannot be negative.';
    }

    const rop = parseInt(formData.reorder_point, 10);
    if (formData.reorder_point === '' || isNaN(rop)) {
      errors.reorder_point = 'Reorder point is required.';
    } else if (rop < 0) {
      errors.reorder_point = 'Reorder point cannot be negative.';
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

    if (editingProduct) {
      // Update
      const result = await updateProduct(editingProduct.id, formData);
      setIsSubmitting(false);

      if (result.success) {
        setIsFormModalOpen(false);
        setSuccessMessage(`Product '${result.data.name}' (SKU: ${result.data.sku}) updated successfully.`);
        fetchProductList();
      } else {
        setFormError(result.error);
      }
    } else {
      // Create
      const result = await createProduct(formData);
      setIsSubmitting(false);

      if (result.success) {
        setIsFormModalOpen(false);
        setSuccessMessage(`Product '${result.data.name}' (SKU: ${result.data.sku}) created successfully.`);
        fetchProductList();
      } else {
        setFormError(result.error);
      }
    }
  };

  // Delete Action
  const handleConfirmDelete = async () => {
    if (!deletingProduct || isDeleting) return;

    setIsDeleting(true);
    setDeleteError('');

    const result = await deleteProduct(deletingProduct.id);
    setIsDeleting(false);

    if (result.success) {
      setSuccessMessage(`Product '${deletingProduct.name}' (SKU: ${deletingProduct.sku}) was deleted.`);
      setDeletingProduct(null);
      fetchProductList();
    } else {
      setDeleteError(result.error);
    }
  };

  // Filtered Products for Search
  const filteredProducts = products.filter((p) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      p.sku.toLowerCase().includes(query) ||
      p.name.toLowerCase().includes(query) ||
      (p.category && p.category.toLowerCase().includes(query))
    );
  });

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col justify-between font-sans selection:bg-[#03D26F]/30 selection:text-white">
      <Navbar />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex-1 w-full space-y-6">
        {/* Banner and Action Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-[#01353e]/60 border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-sm">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#03D26F] bg-[#03D26F]/15 px-2.5 py-0.5 rounded-full border border-[#03D26F]/30">
                Catalog Registry
              </span>
              <span className="text-xs text-[#EAF4F4]/60 font-mono">
                {products.length} {products.length === 1 ? 'Product' : 'Products'} Total
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-2.5">
              <Package className="w-6 h-6 text-[#03D26F]" />
              Product Management
            </h1>
            <p className="text-xs text-[#EAF4F4]/70 mt-1">
              Define catalog items, SKUs, baseline pricing, and automated replenishment thresholds.
            </p>
          </div>

          <button
            type="button"
            onClick={handleOpenCreateModal}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-[#03D26F] hover:bg-[#02be63] text-[#161514] font-bold rounded-xl text-xs transition shadow-lg shadow-[#03D26F]/25 cursor-pointer self-start sm:self-auto shrink-0"
          >
            <Plus className="w-4 h-4 text-[#161514]" />
            <span>Add Product</span>
          </button>
        </div>

        {/* Success Alert */}
        {successMessage && (
          <div
            role="status"
            className="p-4 rounded-2xl bg-[#03D26F]/15 border border-[#03D26F]/30 text-[#03D26F] text-xs flex items-center justify-between gap-2"
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#03D26F] shrink-0" />
              <span className="font-semibold">{successMessage}</span>
            </div>
            <button
              type="button"
              onClick={() => setSuccessMessage('')}
              className="text-[#EAF4F4]/60 hover:text-white cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Global Server Error */}
        {serverError && (
          <div
            role="alert"
            className="p-4 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between gap-2"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{serverError}</span>
            </div>
            <button
              type="button"
              onClick={() => setServerError('')}
              className="text-[#EAF4F4]/60 hover:text-white cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Search & Filter Bar */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative w-full max-w-sm">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#EAF4F4]/40">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              placeholder="Search by SKU, name, or category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-3.5 py-2 bg-[#01353e]/60 border border-white/[0.08] rounded-xl text-xs text-white placeholder-[#EAF4F4]/40 focus:outline-none focus:border-[#03D26F] transition"
            />
          </div>
        </div>

        {/* Products Table */}
        <div className="bg-[#01353e]/50 border border-white/[0.08] rounded-2xl overflow-hidden backdrop-blur-md shadow-sm">
          {isLoading ? (
            <div className="py-20 text-center flex flex-col items-center justify-center gap-3 text-[#EAF4F4]/50">
              <Loader2 className="w-6 h-6 animate-spin text-[#03D26F]" />
              <span className="text-xs">Loading product catalog...</span>
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="py-16 text-center text-[#EAF4F4]/50 space-y-3">
              <div className="w-12 h-12 rounded-full bg-[#01272e] border border-white/[0.08] flex items-center justify-center mx-auto text-[#03D26F]">
                <Package className="w-6 h-6" />
              </div>
              <div className="max-w-sm mx-auto px-4">
                <p className="text-sm font-bold text-white">
                  {searchQuery ? 'No matching products found' : 'No products in catalog yet'}
                </p>
                <p className="text-xs text-[#EAF4F4]/60 mt-1">
                  {searchQuery
                    ? `No products match "${searchQuery}". Clear search or add a new product.`
                    : 'Get started by creating your first catalog product with SKU, pricing, and reorder point.'}
                </p>
              </div>
              {!searchQuery && (
                <button
                  type="button"
                  onClick={handleOpenCreateModal}
                  className="inline-flex items-center gap-1.5 text-xs px-4 py-2 rounded-xl bg-[#03D26F]/15 text-[#03D26F] border border-[#03D26F]/30 hover:bg-[#03D26F]/25 transition font-semibold cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add First Product</span>
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-white/[0.08] bg-[#01272e]/80 text-[#EAF4F4]/70 font-semibold text-[11px] uppercase tracking-wider">
                    <th className="py-3 px-4">SKU</th>
                    <th className="py-3 px-4">Name & Description</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4 text-right">Unit Price</th>
                    <th className="py-3 px-4 text-center">Reorder Point</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.06]">
                  {filteredProducts.map((p) => (
                    <tr
                      key={p.id}
                      className="hover:bg-white/[0.03] transition-colors group"
                    >
                      {/* SKU */}
                      <td className="py-3.5 px-4 font-mono font-bold text-[#03D26F]">
                        <span className="px-2 py-0.5 rounded-lg bg-[#03D26F]/15 border border-[#03D26F]/25">
                          {p.sku}
                        </span>
                      </td>

                      {/* Name & Description */}
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="font-semibold text-white">{p.name}</div>
                        {p.description && (
                          <div className="text-[11px] text-[#EAF4F4]/60 truncate mt-0.5" title={p.description}>
                            {p.description}
                          </div>
                        )}
                      </td>

                      {/* Category */}
                      <td className="py-3.5 px-4">
                        {p.category ? (
                          <span className="inline-block px-2.5 py-0.5 rounded-md text-[11px] bg-[#01272e] text-[#EAF4F4] border border-white/[0.08] font-mono">
                            {p.category}
                          </span>
                        ) : (
                          <span className="text-[#EAF4F4]/30">—</span>
                        )}
                      </td>

                      {/* Unit Price */}
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-[#EAF4F4]">
                        {parseFloat(p.unit_price).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>

                      {/* Reorder Point */}
                      <td className="py-3.5 px-4 text-center font-mono">
                        <span className="px-2 py-0.5 rounded-lg bg-[#01272e] text-[#CEF431] font-bold border border-[#CEF431]/20">
                          {p.reorder_point}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 text-center">
                        {p.is_active ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#03D26F]/15 text-[#03D26F] border border-[#03D26F]/30">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#03D26F]" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-neutral-800 text-[#EAF4F4]/40 border border-white/[0.06]">
                            <span className="w-1.5 h-1.5 rounded-full bg-neutral-500" />
                            Inactive
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleOpenEditModal(p)}
                            className="p-1.5 rounded-lg text-[#EAF4F4]/60 hover:text-[#03D26F] hover:bg-white/[0.06] transition cursor-pointer"
                            title="Edit Product"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setDeletingProduct(p);
                              setDeleteError('');
                            }}
                            className="p-1.5 rounded-lg text-[#EAF4F4]/60 hover:text-rose-400 hover:bg-rose-500/10 transition cursor-pointer"
                            title="Delete Product"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] py-4 text-center text-xs text-[#EAF4F4]/50 bg-[#01272e]">
        SmartSupply AI • Autonomous Inventory Replenishment & Supplier Decision Support System
      </footer>

      {/* ============================================================== */}
      {/* Create / Edit Product Modal */}
      {/* ============================================================== */}
      {isFormModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-[#01353e] border border-white/[0.1] rounded-3xl w-full max-w-lg shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-white/[0.08] bg-[#01272e]/60">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-[#03D26F]/15 rounded-xl text-[#03D26F]">
                  <Package className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight">
                    {editingProduct ? 'Edit Product' : 'Add New Product'}
                  </h3>
                  <p className="text-[11px] text-[#EAF4F4]/60 mt-0.5">
                    {editingProduct ? `Updating SKU: ${editingProduct.sku}` : 'Catalog item specifications'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsFormModalOpen(false)}
                className="text-[#EAF4F4]/60 hover:text-white p-1 rounded-xl hover:bg-white/[0.08] transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Error Alert */}
            {formError && (
              <div className="m-6 mb-0 p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>{formError}</span>
              </div>
            )}

            {/* Modal Form */}
            <form onSubmit={handleFormSubmit} noValidate className="p-6 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* SKU */}
                <div>
                  <label htmlFor="sku" className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1">
                    SKU <span className="text-rose-400">*</span>
                  </label>
                  <input
                    id="sku"
                    name="sku"
                    type="text"
                    value={formData.sku}
                    onChange={handleFormChange}
                    placeholder="e.g. WM-001"
                    disabled={isSubmitting}
                    className={`w-full px-3.5 py-2 bg-[#01272e] border rounded-xl text-xs font-mono text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:ring-1 transition ${
                      fieldErrors.sku
                        ? 'border-rose-500 focus:ring-rose-500/25'
                        : 'border-white/[0.1] focus:border-[#03D26F] focus:ring-[#03D26F]/20'
                    }`}
                  />
                  {fieldErrors.sku && <p className="text-[10px] text-rose-400 mt-1">{fieldErrors.sku}</p>}
                </div>

                {/* Category */}
                <div>
                  <label htmlFor="category" className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1">
                    Category
                  </label>
                  <input
                    id="category"
                    name="category"
                    type="text"
                    value={formData.category}
                    onChange={handleFormChange}
                    placeholder="e.g. Accessories"
                    disabled={isSubmitting}
                    className="w-full px-3.5 py-2 bg-[#01272e] border border-white/[0.1] rounded-xl text-xs text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/20 transition"
                  />
                </div>
              </div>

              {/* Product Name */}
              <div>
                <label htmlFor="name" className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1">
                  Product Name <span className="text-rose-400">*</span>
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={formData.name}
                  onChange={handleFormChange}
                  placeholder="e.g. Wireless Mouse"
                  disabled={isSubmitting}
                  className={`w-full px-3.5 py-2 bg-[#01272e] border rounded-xl text-xs text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:ring-1 transition ${
                    fieldErrors.name
                      ? 'border-rose-500 focus:ring-rose-500/25'
                      : 'border-white/[0.1] focus:border-[#03D26F] focus:ring-[#03D26F]/20'
                  }`}
                />
                {fieldErrors.name && <p className="text-[10px] text-rose-400 mt-1">{fieldErrors.name}</p>}
              </div>

              {/* Description */}
              <div>
                <label htmlFor="description" className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1">
                  Description
                </label>
                <textarea
                  id="description"
                  name="description"
                  rows="2"
                  value={formData.description}
                  onChange={handleFormChange}
                  placeholder="Optional details, dimensions, compatibility..."
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2 bg-[#01272e] border border-white/[0.1] rounded-xl text-xs text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:border-[#03D26F] focus:ring-1 focus:ring-[#03D26F]/20 transition resize-none"
                />
              </div>

              {/* Unit Price & Reorder Point */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="unit_price" className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1">
                    Unit Price (LKR / USD) <span className="text-rose-400">*</span>
                  </label>
                  <input
                    id="unit_price"
                    name="unit_price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={formData.unit_price}
                    onChange={handleFormChange}
                    placeholder="2500.00"
                    disabled={isSubmitting}
                    className={`w-full px-3.5 py-2 bg-[#01272e] border rounded-xl text-xs font-mono text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:ring-1 transition ${
                      fieldErrors.unit_price
                        ? 'border-rose-500 focus:ring-rose-500/25'
                        : 'border-white/[0.1] focus:border-[#03D26F] focus:ring-[#03D26F]/20'
                    }`}
                  />
                  {fieldErrors.unit_price && (
                    <p className="text-[10px] text-rose-400 mt-1">{fieldErrors.unit_price}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="reorder_point" className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1">
                    Reorder Point <span className="text-rose-400">*</span>
                  </label>
                  <input
                    id="reorder_point"
                    name="reorder_point"
                    type="number"
                    step="1"
                    min="0"
                    value={formData.reorder_point}
                    onChange={handleFormChange}
                    placeholder="25"
                    disabled={isSubmitting}
                    className={`w-full px-3.5 py-2 bg-[#01272e] border rounded-xl text-xs font-mono text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:ring-1 transition ${
                      fieldErrors.reorder_point
                        ? 'border-rose-500 focus:ring-rose-500/25'
                        : 'border-white/[0.1] focus:border-[#03D26F] focus:ring-[#03D26F]/20'
                    }`}
                  />
                  {fieldErrors.reorder_point && (
                    <p className="text-[10px] text-rose-400 mt-1">{fieldErrors.reorder_point}</p>
                  )}
                </div>
              </div>

              {/* Status Toggle (For Edit Mode) */}
              {editingProduct && (
                <div className="pt-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      name="is_active"
                      checked={formData.is_active}
                      onChange={handleFormChange}
                      disabled={isSubmitting}
                      className="w-4 h-4 rounded border-neutral-700 bg-[#01272e] text-[#03D26F] focus:ring-[#03D26F]/30"
                    />
                    <span className="text-xs text-[#EAF4F4]/90 font-medium">Catalog Active Status</span>
                  </label>
                </div>
              )}

              {/* Modal Actions */}
              <div className="pt-4 flex items-center justify-end gap-2 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setIsFormModalOpen(false)}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl text-xs text-[#EAF4F4]/60 hover:text-white transition font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 bg-[#03D26F] hover:bg-[#02be63] disabled:opacity-50 disabled:cursor-not-allowed text-[#161514] font-bold rounded-xl text-xs transition shadow-lg shadow-[#03D26F]/25 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-[#161514]" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>{editingProduct ? 'Save Changes' : 'Create Product'}</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* Delete Confirmation Modal */}
      {/* ============================================================== */}
      {deletingProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-[#01353e] border border-white/[0.1] rounded-3xl w-full max-w-md shadow-2xl p-6 sm:p-8 space-y-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/15 flex items-center justify-center text-rose-400 mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1">
              <h3 className="text-base font-bold text-white tracking-tight">Delete Product</h3>
              <p className="text-xs text-[#EAF4F4]/70 leading-relaxed">
                Are you sure you want to delete <strong className="text-white">{deletingProduct.name}</strong> (SKU:{' '}
                <span className="font-mono text-[#03D26F] font-bold">{deletingProduct.sku}</span>)?
              </p>
              <p className="text-[11px] text-rose-400/90 font-mono pt-1">
                This action cannot be undone.
              </p>
            </div>

            {deleteError && (
              <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>{deleteError}</span>
              </div>
            )}

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingProduct(null)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl text-xs text-[#EAF4F4]/60 hover:text-white transition font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl text-xs transition shadow-lg shadow-rose-600/25 cursor-pointer"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Product</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
