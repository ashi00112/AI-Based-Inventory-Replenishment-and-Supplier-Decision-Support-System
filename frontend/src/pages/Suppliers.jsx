import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Truck,
  Plus,
  Pencil,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  Search,
  Building2,
  Tag,
  Clock,
  Layers,
  Phone,
  Mail,
  MapPin,
  DollarSign,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getProducts } from '../services/productApi';
import {
  getSuppliers,
  createSupplier,
  updateSupplier,
  deleteSupplier,
} from '../services/supplierApi';
import {
  getProductSuppliers,
  createProductSupplier,
  updateProductSupplier,
  deleteProductSupplier,
} from '../services/productSupplierApi';
import Navbar from '../components/Navbar';

export default function Suppliers() {
  const { user } = useAuth();

  // Active Tab: 'suppliers' | 'offers'
  const [activeTab, setActiveTab] = useState('suppliers');

  // Supplier State
  const [suppliers, setSuppliers] = useState([]);
  const [isLoadingSuppliers, setIsLoadingSuppliers] = useState(true);
  const [supplierSearch, setSupplierSearch] = useState('');
  const [supplierStatusFilter, setSupplierStatusFilter] = useState('');

  // Commercial Offers State
  const [offers, setOffers] = useState([]);
  const [isLoadingOffers, setIsLoadingOffers] = useState(true);
  const [offerProductFilter, setOfferProductFilter] = useState('');
  const [offerSupplierFilter, setOfferSupplierFilter] = useState('');
  const [offerStatusFilter, setOfferStatusFilter] = useState('');

  // Products reference for offer creation & filtering
  const [productsList, setProductsList] = useState([]);

  // Feedback Messages
  const [serverError, setServerError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Supplier Modal State
  const [isSupplierModalOpen, setIsSupplierModalOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [isSubmittingSupplier, setIsSubmittingSupplier] = useState(false);
  const [supplierFormError, setSupplierFormError] = useState('');
  const [supplierForm, setSupplierForm] = useState({
    supplier_code: '',
    name: '',
    contact_name: '',
    email: '',
    phone: '',
    address: '',
    is_active: true,
  });

  // Supplier Delete Modal State
  const [deletingSupplier, setDeletingSupplier] = useState(null);
  const [isDeletingSupplier, setIsDeletingSupplier] = useState(false);

  // Offer Modal State
  const [isOfferModalOpen, setIsOfferModalOpen] = useState(false);
  const [editingOffer, setEditingOffer] = useState(null);
  const [isSubmittingOffer, setIsSubmittingOffer] = useState(false);
  const [offerFormError, setOfferFormError] = useState('');
  const [offerForm, setOfferForm] = useState({
    product_id: '',
    supplier_id: '',
    supplier_sku: '',
    unit_cost: '',
    moq: '1',
    lead_time_days: '0',
    is_active: true,
  });

  // Offer Delete Modal State
  const [deletingOffer, setDeletingOffer] = useState(null);
  const [isDeletingOffer, setIsDeletingOffer] = useState(false);

  // Auto-dismiss success notification
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Load Suppliers
  const fetchSuppliers = useCallback(async () => {
    setIsLoadingSuppliers(true);
    setServerError('');
    const params = {};
    if (supplierStatusFilter !== '') {
      params.isActive = supplierStatusFilter === 'true';
    }
    if (supplierSearch.trim()) {
      params.search = supplierSearch.trim();
    }
    const res = await getSuppliers(params);
    if (res.success) {
      setSuppliers(res.data);
    } else {
      setServerError(res.error);
    }
    setIsLoadingSuppliers(false);
  }, [supplierStatusFilter, supplierSearch]);

  // Load Offers
  const fetchOffers = useCallback(async () => {
    setIsLoadingOffers(true);
    setServerError('');
    const params = { limit: 200 };
    if (offerProductFilter) params.productId = parseInt(offerProductFilter, 10);
    if (offerSupplierFilter) params.supplierId = parseInt(offerSupplierFilter, 10);
    if (offerStatusFilter !== '') {
      params.isActive = offerStatusFilter === 'true';
    }
    const res = await getProductSuppliers(params);
    if (res.success) {
      setOffers(res.data);
    } else {
      setServerError(res.error);
    }
    setIsLoadingOffers(false);
  }, [offerProductFilter, offerSupplierFilter, offerStatusFilter]);

  // Load Products for selectors
  const fetchProducts = useCallback(async () => {
    const res = await getProducts({ limit: 500 });
    if (res.success) {
      setProductsList(res.data);
    }
  }, []);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

  useEffect(() => {
    fetchOffers();
  }, [fetchOffers]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // Open Add Supplier Modal
  const handleOpenAddSupplier = () => {
    setEditingSupplier(null);
    setSupplierForm({
      supplier_code: '',
      name: '',
      contact_name: '',
      email: '',
      phone: '',
      address: '',
      is_active: true,
    });
    setSupplierFormError('');
    setIsSupplierModalOpen(true);
  };

  // Open Edit Supplier Modal
  const handleOpenEditSupplier = (sup) => {
    setEditingSupplier(sup);
    setSupplierForm({
      supplier_code: sup.supplier_code,
      name: sup.name,
      contact_name: sup.contact_name || '',
      email: sup.email || '',
      phone: sup.phone || '',
      address: sup.address || '',
      is_active: sup.is_active,
    });
    setSupplierFormError('');
    setIsSupplierModalOpen(true);
  };

  // Handle Save Supplier
  const handleSaveSupplier = async (e) => {
    e.preventDefault();
    setSupplierFormError('');
    if (!supplierForm.supplier_code.trim()) {
      setSupplierFormError('Supplier code is required.');
      return;
    }
    if (!supplierForm.name.trim()) {
      setSupplierFormError('Supplier name is required.');
      return;
    }

    setIsSubmittingSupplier(true);
    const payload = {
      supplier_code: supplierForm.supplier_code.trim(),
      name: supplierForm.name.trim(),
      contact_name: supplierForm.contact_name.trim() || null,
      email: supplierForm.email.trim() || null,
      phone: supplierForm.phone.trim() || null,
      address: supplierForm.address.trim() || null,
      is_active: supplierForm.is_active,
    };

    let res;
    if (editingSupplier) {
      res = await updateSupplier(editingSupplier.id, payload);
    } else {
      res = await createSupplier(payload);
    }

    if (res.success) {
      setIsSupplierModalOpen(false);
      setSuccessMessage(
        editingSupplier
          ? `Supplier ${payload.supplier_code} updated successfully.`
          : `Supplier ${payload.supplier_code} registered successfully.`
      );
      fetchSuppliers();
    } else {
      setSupplierFormError(res.error);
    }
    setIsSubmittingSupplier(false);
  };

  // Handle Delete Supplier
  const handleConfirmDeleteSupplier = async () => {
    if (!deletingSupplier) return;
    setIsDeletingSupplier(true);
    const res = await deleteSupplier(deletingSupplier.id);
    if (res.success) {
      setSuccessMessage(`Supplier ${deletingSupplier.supplier_code} and all related offers removed.`);
      setDeletingSupplier(null);
      fetchSuppliers();
      fetchOffers();
    } else {
      setServerError(res.error);
      setDeletingSupplier(null);
    }
    setIsDeletingSupplier(false);
  };

  // Open Add Offer Modal
  const handleOpenAddOffer = () => {
    setEditingOffer(null);
    setOfferForm({
      product_id: productsList[0]?.id ? String(productsList[0].id) : '',
      supplier_id: suppliers[0]?.id ? String(suppliers[0].id) : '',
      supplier_sku: '',
      unit_cost: '',
      moq: '1',
      lead_time_days: '0',
      is_active: true,
    });
    setOfferFormError('');
    setIsOfferModalOpen(true);
  };

  // Open Edit Offer Modal
  const handleOpenEditOffer = (offer) => {
    setEditingOffer(offer);
    setOfferForm({
      product_id: String(offer.product_id),
      supplier_id: String(offer.supplier_id),
      supplier_sku: offer.supplier_sku || '',
      unit_cost: String(offer.unit_cost),
      moq: String(offer.moq),
      lead_time_days: String(offer.lead_time_days),
      is_active: offer.is_active,
    });
    setOfferFormError('');
    setIsOfferModalOpen(true);
  };

  // Handle Save Offer
  const handleSaveOffer = async (e) => {
    e.preventDefault();
    setOfferFormError('');

    const costNum = parseFloat(offerForm.unit_cost);
    if (isNaN(costNum) || costNum < 0) {
      setOfferFormError('Unit cost must be a non-negative number.');
      return;
    }
    const moqNum = parseInt(offerForm.moq, 10);
    if (isNaN(moqNum) || moqNum < 1) {
      setOfferFormError('Minimum order quantity (MOQ) must be at least 1.');
      return;
    }
    const leadNum = parseInt(offerForm.lead_time_days, 10);
    if (isNaN(leadNum) || leadNum < 0) {
      setOfferFormError('Lead time must be at least 0 days.');
      return;
    }

    setIsSubmittingOffer(true);

    if (editingOffer) {
      const payload = {
        supplier_sku: offerForm.supplier_sku.trim() || null,
        unit_cost: costNum,
        moq: moqNum,
        lead_time_days: leadNum,
        is_active: offerForm.is_active,
      };
      const res = await updateProductSupplier(editingOffer.id, payload);
      if (res.success) {
        setIsOfferModalOpen(false);
        setSuccessMessage('Commercial offer updated successfully.');
        fetchOffers();
      } else {
        setOfferFormError(res.error);
      }
    } else {
      const payload = {
        product_id: parseInt(offerForm.product_id, 10),
        supplier_id: parseInt(offerForm.supplier_id, 10),
        supplier_sku: offerForm.supplier_sku.trim() || null,
        unit_cost: costNum,
        moq: moqNum,
        lead_time_days: leadNum,
        is_active: offerForm.is_active,
      };
      const res = await createProductSupplier(payload);
      if (res.success) {
        setIsOfferModalOpen(false);
        setSuccessMessage('Commercial offer established successfully.');
        fetchOffers();
      } else {
        setOfferFormError(res.error);
      }
    }
    setIsSubmittingOffer(false);
  };

  // Handle Delete Offer
  const handleConfirmDeleteOffer = async () => {
    if (!deletingOffer) return;
    setIsDeletingOffer(true);
    const res = await deleteProductSupplier(deletingOffer.id);
    if (res.success) {
      setSuccessMessage('Commercial offer removed.');
      setDeletingOffer(null);
      fetchOffers();
    } else {
      setServerError(res.error);
      setDeletingOffer(null);
    }
    setIsDeletingOffer(false);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Page Header */}
        <section className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/[0.06] pb-6">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-violet-400 mb-1">
              <Truck className="w-4 h-4" />
              <span>SmartSupply Electronics Procurement</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Supplier & Commercial Terms
            </h1>
            <p className="text-xs text-neutral-400 mt-1">
              Manage authorized merchandise vendors and their product-specific wholesale commercial terms (Unit Cost, MOQ, Lead Time).
            </p>
          </div>

          <div className="flex items-center gap-3">
            {activeTab === 'suppliers' ? (
              <button
                type="button"
                onClick={handleOpenAddSupplier}
                className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-violet-600/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Add Supplier</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleOpenAddOffer}
                disabled={suppliers.length === 0 || productsList.length === 0}
                className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-lg shadow-violet-600/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Add Commercial Offer</span>
              </button>
            )}
          </div>
        </section>

        {/* Global Feedback Notifications */}
        {serverError && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{serverError}</span>
            </div>
            <button type="button" onClick={() => setServerError('')} className="text-red-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successMessage}</span>
            </div>
            <button type="button" onClick={() => setSuccessMessage('')} className="text-emerald-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-2 border-b border-white/[0.06] pb-1">
          <button
            type="button"
            onClick={() => setActiveTab('suppliers')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'suppliers'
                ? 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
                : 'text-neutral-400 hover:text-white hover:bg-white/[0.03]'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            <span>Vendors Directory</span>
            <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-neutral-800 text-neutral-300 font-mono">
              {suppliers.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('offers')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'offers'
                ? 'bg-violet-500/15 text-violet-300 border border-violet-500/30'
                : 'text-neutral-400 hover:text-white hover:bg-white/[0.03]'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Product Commercial Terms</span>
            <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-neutral-800 text-neutral-300 font-mono">
              {offers.length}
            </span>
          </button>
        </div>

        {/* TAB 1: SUPPLIERS DIRECTORY */}
        {activeTab === 'suppliers' && (
          <div className="space-y-4">
            {/* Filters Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-neutral-900/40 border border-white/[0.06] p-3 rounded-xl">
              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search code, name, contact..."
                  value={supplierSearch}
                  onChange={(e) => setSupplierSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-neutral-950 border border-white/[0.06] rounded-lg text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-violet-500/40"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <select
                  value={supplierStatusFilter}
                  onChange={(e) => setSupplierStatusFilter(e.target.value)}
                  className="w-full sm:w-auto px-3 py-1.5 bg-neutral-950 border border-white/[0.06] rounded-lg text-xs text-neutral-200 focus:outline-none focus:border-violet-500/40"
                >
                  <option value="">All Statuses</option>
                  <option value="true">Active Only</option>
                  <option value="false">Inactive Only</option>
                </select>
              </div>
            </div>

            {/* Suppliers Table */}
            <div className="bg-neutral-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.06] bg-neutral-900/60 text-neutral-500 font-medium uppercase tracking-wider text-[10px]">
                      <th className="py-3 px-4">Code</th>
                      <th className="py-3 px-4">Supplier Name</th>
                      <th className="py-3 px-4">Contact Person</th>
                      <th className="py-3 px-4">Contact Info</th>
                      <th className="py-3 px-4">Address</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {isLoadingSuppliers ? (
                      <tr>
                        <td colSpan="7" className="py-12 text-center text-neutral-500">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
                            <span>Loading supplier directory...</span>
                          </div>
                        </td>
                      </tr>
                    ) : suppliers.length === 0 ? (
                      <tr>
                        <td colSpan="7" className="py-12 text-center text-neutral-500">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Building2 className="w-8 h-8 text-neutral-700" />
                            <span>No suppliers registered yet. Click "Add Supplier" to register one.</span>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      suppliers.map((sup) => (
                        <tr key={sup.id} className="hover:bg-white/[0.02] transition-colors">
                          <td className="py-3 px-4 font-mono font-bold text-violet-400 whitespace-nowrap">
                            {sup.supplier_code}
                          </td>
                          <td className="py-3 px-4 font-medium text-white whitespace-nowrap">
                            {sup.name}
                          </td>
                          <td className="py-3 px-4 text-neutral-300">
                            {sup.contact_name || <span className="text-neutral-600">—</span>}
                          </td>
                          <td className="py-3 px-4 space-y-0.5">
                            {sup.email && (
                              <div className="flex items-center gap-1.5 text-neutral-300">
                                <Mail className="w-3 h-3 text-neutral-500" />
                                <span>{sup.email}</span>
                              </div>
                            )}
                            {sup.phone && (
                              <div className="flex items-center gap-1.5 text-neutral-400">
                                <Phone className="w-3 h-3 text-neutral-500" />
                                <span>{sup.phone}</span>
                              </div>
                            )}
                            {!sup.email && !sup.phone && <span className="text-neutral-600">—</span>}
                          </td>
                          <td className="py-3 px-4 text-neutral-400 max-w-xs truncate">
                            {sup.address || <span className="text-neutral-600">—</span>}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                                sup.is_active
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : 'bg-neutral-800 text-neutral-400 border border-neutral-700'
                              }`}
                            >
                              {sup.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1">
                              <button
                                type="button"
                                onClick={() => handleOpenEditSupplier(sup)}
                                className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition"
                                title="Edit Supplier"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeletingSupplier(sup)}
                                className="p-1.5 rounded-lg text-neutral-400 hover:text-red-400 hover:bg-red-500/[0.08] transition"
                                title="Delete Supplier"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: PRODUCT-SUPPLIER COMMERCIAL OFFERS */}
        {activeTab === 'offers' && (
          <div className="space-y-4">
            {/* Filters Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-neutral-900/40 border border-white/[0.06] p-3 rounded-xl">
              <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                {/* Filter Product */}
                <select
                  value={offerProductFilter}
                  onChange={(e) => setOfferProductFilter(e.target.value)}
                  className="px-3 py-1.5 bg-neutral-950 border border-white/[0.06] rounded-lg text-xs text-neutral-200 focus:outline-none focus:border-violet-500/40"
                >
                  <option value="">All Products</option>
                  {productsList.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.sku} - {p.name}
                    </option>
                  ))}
                </select>

                {/* Filter Supplier */}
                <select
                  value={offerSupplierFilter}
                  onChange={(e) => setOfferSupplierFilter(e.target.value)}
                  className="px-3 py-1.5 bg-neutral-950 border border-white/[0.06] rounded-lg text-xs text-neutral-200 focus:outline-none focus:border-violet-500/40"
                >
                  <option value="">All Suppliers</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.supplier_code} - {s.name}
                    </option>
                  ))}
                </select>

                {/* Filter Status */}
                <select
                  value={offerStatusFilter}
                  onChange={(e) => setOfferStatusFilter(e.target.value)}
                  className="px-3 py-1.5 bg-neutral-950 border border-white/[0.06] rounded-lg text-xs text-neutral-200 focus:outline-none focus:border-violet-500/40"
                >
                  <option value="">All Statuses</option>
                  <option value="true">Active Offers</option>
                  <option value="false">Inactive Offers</option>
                </select>
              </div>
            </div>

            {/* Offers Table */}
            <div className="bg-neutral-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.06] bg-neutral-900/60 text-neutral-500 font-medium uppercase tracking-wider text-[10px]">
                      <th className="py-3 px-4">Product SKU</th>
                      <th className="py-3 px-4">Product Title</th>
                      <th className="py-3 px-4">Supplier</th>
                      <th className="py-3 px-4">Supplier SKU</th>
                      <th className="py-3 px-4 text-right">Unit Cost (LKR)</th>
                      <th className="py-3 px-4 text-right">MOQ</th>
                      <th className="py-3 px-4 text-right">Lead Time</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {isLoadingOffers ? (
                      <tr>
                        <td colSpan="9" className="py-12 text-center text-neutral-500">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
                            <span>Loading commercial offers...</span>
                          </div>
                        </td>
                      </tr>
                    ) : offers.length === 0 ? (
                      <tr>
                        <td colSpan="9" className="py-12 text-center text-neutral-500">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Layers className="w-8 h-8 text-neutral-700" />
                            <span>No commercial offers match current filters. Click "Add Commercial Offer" to create one.</span>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      offers.map((offer) => (
                        <tr key={offer.id} className="hover:bg-white/[0.02] transition-colors">
                          <td className="py-3 px-4 font-mono font-medium text-violet-400 whitespace-nowrap">
                            {offer.product?.sku || `Prod #${offer.product_id}`}
                          </td>
                          <td className="py-3 px-4 font-medium text-white max-w-xs truncate">
                            {offer.product?.name || '—'}
                          </td>
                          <td className="py-3 px-4 whitespace-nowrap">
                            <span className="font-mono text-emerald-400 font-semibold mr-1.5">
                              {offer.supplier?.supplier_code}
                            </span>
                            <span className="text-neutral-300">
                              {offer.supplier?.name}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono text-neutral-400">
                            {offer.supplier_sku || <span className="text-neutral-600">—</span>}
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-bold text-white">
                            Rs. {parseFloat(offer.unit_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-neutral-300">
                            {offer.moq} units
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-neutral-300 whitespace-nowrap">
                            {offer.lead_time_days} days
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                                offer.is_active
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : 'bg-neutral-800 text-neutral-400 border border-neutral-700'
                              }`}
                            >
                              {offer.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1">
                              <button
                                type="button"
                                onClick={() => handleOpenEditOffer(offer)}
                                className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition"
                                title="Edit Offer"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeletingOffer(offer)}
                                className="p-1.5 rounded-lg text-neutral-400 hover:text-red-400 hover:bg-red-500/[0.08] transition"
                                title="Delete Offer"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* MODAL: ADD / EDIT SUPPLIER */}
      {isSupplierModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-white/[0.08] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Building2 className="w-4 h-4 text-violet-400" />
                {editingSupplier ? 'Edit Vendor Profile' : 'Register New Vendor'}
              </h3>
              <button
                type="button"
                onClick={() => setIsSupplierModalOpen(false)}
                className="text-neutral-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {supplierFormError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-300 rounded-lg text-xs">
                {supplierFormError}
              </div>
            )}

            <form onSubmit={handleSaveSupplier} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-neutral-400 mb-1">
                    Supplier Code <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. SUP-001"
                    value={supplierForm.supplier_code}
                    onChange={(e) =>
                      setSupplierForm((prev) => ({ ...prev, supplier_code: e.target.value.toUpperCase() }))
                    }
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white font-mono uppercase focus:outline-none focus:border-violet-500/40"
                  />
                </div>
                <div>
                  <label className="block text-neutral-400 mb-1">
                    Company Name <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Legal business name"
                    value={supplierForm.name}
                    onChange={(e) => setSupplierForm((prev) => ({ ...prev, name: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                  />
                </div>
              </div>

              <div>
                <label className="block text-neutral-400 mb-1">Contact Person Name</label>
                <input
                  type="text"
                  placeholder="Primary contact / Account manager"
                  value={supplierForm.contact_name}
                  onChange={(e) => setSupplierForm((prev) => ({ ...prev, contact_name: e.target.value }))}
                  className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-neutral-400 mb-1">Email Address</label>
                  <input
                    type="email"
                    placeholder="orders@vendor.lk"
                    value={supplierForm.email}
                    onChange={(e) => setSupplierForm((prev) => ({ ...prev, email: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                  />
                </div>
                <div>
                  <label className="block text-neutral-400 mb-1">Telephone Number</label>
                  <input
                    type="tel"
                    placeholder="+94 11 ..."
                    value={supplierForm.phone}
                    onChange={(e) => setSupplierForm((prev) => ({ ...prev, phone: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                  />
                </div>
              </div>

              <div>
                <label className="block text-neutral-400 mb-1">Physical / Postal Address</label>
                <textarea
                  rows="2"
                  placeholder="Office / Warehouse address"
                  value={supplierForm.address}
                  onChange={(e) => setSupplierForm((prev) => ({ ...prev, address: e.target.value }))}
                  className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="sup-active"
                  checked={supplierForm.is_active}
                  onChange={(e) => setSupplierForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                  className="rounded border-white/[0.1] bg-neutral-950 text-violet-600 focus:ring-0"
                />
                <label htmlFor="sup-active" className="text-neutral-300 font-medium">
                  Active Vendor Status (eligible for replenishment procurement)
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setIsSupplierModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.04] transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingSupplier}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg font-medium transition"
                >
                  {isSubmittingSupplier && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{editingSupplier ? 'Save Changes' : 'Register Vendor'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: DELETE SUPPLIER CONFIRMATION */}
      {deletingSupplier && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-red-500/20 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/10 text-red-400">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">Delete Supplier?</h4>
                <p className="text-xs text-neutral-400 font-mono">{deletingSupplier.supplier_code}</p>
              </div>
            </div>

            <p className="text-xs text-neutral-300 leading-relaxed">
              Are you sure you want to delete <span className="text-white font-medium">{deletingSupplier.name}</span>?
              All commercial offers associated with this supplier will also be removed.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setDeletingSupplier(null)}
                className="px-3.5 py-1.5 rounded-lg text-neutral-400 hover:text-white text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteSupplier}
                disabled={isDeletingSupplier}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold"
              >
                {isDeletingSupplier && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Delete Supplier</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: ADD / EDIT PRODUCT-SUPPLIER OFFER */}
      {isOfferModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-white/[0.08] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-violet-400" />
                {editingOffer ? 'Update Commercial Offer' : 'Establish Commercial Offer'}
              </h3>
              <button
                type="button"
                onClick={() => setIsOfferModalOpen(false)}
                className="text-neutral-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {offerFormError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-300 rounded-lg text-xs">
                {offerFormError}
              </div>
            )}

            <form onSubmit={handleSaveOffer} className="space-y-3.5 text-xs">
              {/* Product and Supplier selectors */}
              {editingOffer ? (
                <div className="p-3 rounded-lg bg-neutral-950/60 border border-white/[0.06] space-y-1">
                  <div className="flex justify-between text-neutral-400">
                    <span>Product:</span>
                    <span className="font-semibold text-white">
                      {editingOffer.product?.sku} - {editingOffer.product?.name}
                    </span>
                  </div>
                  <div className="flex justify-between text-neutral-400">
                    <span>Supplier:</span>
                    <span className="font-semibold text-emerald-400">
                      {editingOffer.supplier?.supplier_code} - {editingOffer.supplier?.name}
                    </span>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-neutral-400 mb-1">
                      Target Catalog Product <span className="text-violet-400">*</span>
                    </label>
                    <select
                      required
                      value={offerForm.product_id}
                      onChange={(e) => setOfferForm((prev) => ({ ...prev, product_id: e.target.value }))}
                      className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                    >
                      {productsList.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.sku} — {p.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-neutral-400 mb-1">
                      Supplying Vendor <span className="text-violet-400">*</span>
                    </label>
                    <select
                      required
                      value={offerForm.supplier_id}
                      onChange={(e) => setOfferForm((prev) => ({ ...prev, supplier_id: e.target.value }))}
                      className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white focus:outline-none focus:border-violet-500/40"
                    >
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.supplier_code} — {s.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              <div>
                <label className="block text-neutral-400 mb-1">Supplier Part / Item SKU (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. VEND-WM-202"
                  value={offerForm.supplier_sku}
                  onChange={(e) => setOfferForm((prev) => ({ ...prev, supplier_sku: e.target.value }))}
                  className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white font-mono focus:outline-none focus:border-violet-500/40"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-neutral-400 mb-1">
                    Unit Cost (Rs.) <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="0.00"
                    value={offerForm.unit_cost}
                    onChange={(e) => setOfferForm((prev) => ({ ...prev, unit_cost: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white font-mono focus:outline-none focus:border-violet-500/40"
                  />
                </div>
                <div>
                  <label className="block text-neutral-400 mb-1">
                    MOQ (Units) <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    placeholder="1"
                    value={offerForm.moq}
                    onChange={(e) => setOfferForm((prev) => ({ ...prev, moq: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white font-mono focus:outline-none focus:border-violet-500/40"
                  />
                </div>
                <div>
                  <label className="block text-neutral-400 mb-1">
                    Lead Time (Days) <span className="text-violet-400">*</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    required
                    placeholder="0"
                    value={offerForm.lead_time_days}
                    onChange={(e) => setOfferForm((prev) => ({ ...prev, lead_time_days: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-white/[0.08] rounded-lg text-white font-mono focus:outline-none focus:border-violet-500/40"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="offer-active"
                  checked={offerForm.is_active}
                  onChange={(e) => setOfferForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                  className="rounded border-white/[0.1] bg-neutral-950 text-violet-600 focus:ring-0"
                />
                <label htmlFor="offer-active" className="text-neutral-300 font-medium">
                  Active Offer (available for replenishment procurement decisions)
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setIsOfferModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.04] transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingOffer}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg font-medium transition"
                >
                  {isSubmittingOffer && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{editingOffer ? 'Save Terms' : 'Create Offer'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: DELETE OFFER CONFIRMATION */}
      {deletingOffer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-red-500/20 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/10 text-red-400">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">Remove Commercial Offer?</h4>
                <p className="text-xs text-neutral-400 font-mono">
                  {deletingOffer.product?.sku} ↔ {deletingOffer.supplier?.supplier_code}
                </p>
              </div>
            </div>

            <p className="text-xs text-neutral-300 leading-relaxed">
              Are you sure you want to remove the commercial offer from{' '}
              <span className="text-white font-medium">{deletingOffer.supplier?.name}</span> for{' '}
              <span className="text-white font-medium">{deletingOffer.product?.name}</span>?
              Neither the Product nor the Supplier will be deleted.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setDeletingOffer(null)}
                className="px-3.5 py-1.5 rounded-lg text-neutral-400 hover:text-white text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteOffer}
                disabled={isDeletingOffer}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold"
              >
                {isDeletingOffer && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Remove Offer</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
