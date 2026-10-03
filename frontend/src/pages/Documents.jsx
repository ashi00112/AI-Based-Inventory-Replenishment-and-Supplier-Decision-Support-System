import React, { useState, useEffect, useMemo } from 'react';
import {
  FileText,
  Upload,
  Search,
  Filter,
  Download,
  Trash2,
  Edit,
  CheckCircle,
  AlertCircle,
  X,
  FileCheck,
  Building2,
  Calendar,
  HardDrive,
  RefreshCw,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import {
  getDocuments,
  uploadDocument,
  updateDocument,
  downloadDocument,
  deleteDocument,
} from '../services/documentApi';
import { getSuppliers } from '../services/supplierApi';

const DOCUMENT_TYPES = [
  { value: 'procurement_policy', label: 'Procurement Policy', supplierRule: 'none' },
  { value: 'inventory_replenishment_policy', label: 'Replenishment Policy', supplierRule: 'none' },
  { value: 'supplier_sla', label: 'Supplier SLA', supplierRule: 'required' },
  { value: 'supplier_contract', label: 'Supplier Contract', supplierRule: 'required' },
  { value: 'supplier_performance_report', label: 'Performance Report', supplierRule: 'required' },
  { value: 'other', label: 'Other Document', supplierRule: 'optional' },
];

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState('');
  const [selectedSupplierFilter, setSelectedSupplierFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Modals
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);

  // Upload Form State
  const [uploadForm, setUploadForm] = useState({
    title: '',
    document_type: 'procurement_policy',
    supplier_id: '',
    file: null,
  });
  const [uploadFileName, setUploadFileName] = useState('');

  // Edit Form State
  const [editForm, setEditForm] = useState({
    title: '',
    document_type: '',
    supplier_id: '',
    is_active: true,
  });

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [docsRes, supsRes] = await Promise.all([
        getDocuments({
          documentType: selectedTypeFilter || undefined,
          supplierId: selectedSupplierFilter ? parseInt(selectedSupplierFilter, 10) : undefined,
          isActive: statusFilter === '' ? undefined : statusFilter === 'active',
          search: searchTerm || undefined,
        }),
        getSuppliers({ limit: 200, isActive: true }),
      ]);

      if (!docsRes.success) {
        setError(docsRes.error);
      } else {
        setDocuments(docsRes.data);
      }

      if (supsRes.success) {
        setSuppliers(supsRes.data);
      }
    } catch (err) {
      setError('Failed to load document management data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedTypeFilter, selectedSupplierFilter, statusFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchData();
  };

  const handleOpenUploadModal = () => {
    setUploadForm({
      title: '',
      document_type: 'procurement_policy',
      supplier_id: '',
      file: null,
    });
    setUploadFileName('');
    setError(null);
    setUploadModalOpen(true);
  };

  const handleUploadTypeChange = (e) => {
    const newType = e.target.value;
    const typeDef = DOCUMENT_TYPES.find((t) => t.value === newType);
    setUploadForm((prev) => ({
      ...prev,
      document_type: newType,
      supplier_id: typeDef?.supplierRule === 'none' ? '' : prev.supplier_id,
    }));
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) {
      setUploadForm((prev) => ({ ...prev, file: null }));
      setUploadFileName('');
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF file (.pdf extension).');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('Selected PDF exceeds the 10 MB maximum upload limit.');
      return;
    }

    setError(null);
    setUploadForm((prev) => ({ ...prev, file }));
    setUploadFileName(file.name);
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadForm.title.trim()) {
      setError('Please enter a document title.');
      return;
    }

    if (!uploadForm.file) {
      setError('Please select a PDF file to upload.');
      return;
    }

    const typeDef = DOCUMENT_TYPES.find((t) => t.value === uploadForm.document_type);
    if (typeDef?.supplierRule === 'required' && !uploadForm.supplier_id) {
      setError(`A supplier must be selected for documents of type "${typeDef.label}".`);
      return;
    }

    setActionLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('title', uploadForm.title.trim());
    formData.append('document_type', uploadForm.document_type);
    if (uploadForm.supplier_id) {
      formData.append('supplier_id', uploadForm.supplier_id);
    }
    formData.append('file', uploadForm.file);

    const res = await uploadDocument(formData);
    setActionLoading(false);

    if (!res.success) {
      setError(res.error);
    } else {
      setSuccessMsg(`Document "${res.data.title}" uploaded successfully.`);
      setUploadModalOpen(false);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 4000);
    }
  };

  const handleOpenEditModal = (doc) => {
    setSelectedDoc(doc);
    setEditForm({
      title: doc.title,
      document_type: doc.document_type,
      supplier_id: doc.supplier_id ? String(doc.supplier_id) : '',
      is_active: doc.is_active,
    });
    setError(null);
    setEditModalOpen(true);
  };

  const handleEditTypeChange = (e) => {
    const newType = e.target.value;
    const typeDef = DOCUMENT_TYPES.find((t) => t.value === newType);
    setEditForm((prev) => ({
      ...prev,
      document_type: newType,
      supplier_id: typeDef?.supplierRule === 'none' ? '' : prev.supplier_id,
    }));
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editForm.title.trim()) {
      setError('Document title cannot be empty.');
      return;
    }

    const typeDef = DOCUMENT_TYPES.find((t) => t.value === editForm.document_type);
    if (typeDef?.supplierRule === 'required' && !editForm.supplier_id) {
      setError(`A supplier must be selected for documents of type "${typeDef.label}".`);
      return;
    }

    setActionLoading(true);
    setError(null);

    const payload = {
      title: editForm.title.trim(),
      document_type: editForm.document_type,
      supplier_id: editForm.supplier_id ? parseInt(editForm.supplier_id, 10) : null,
      is_active: editForm.is_active,
    };

    const res = await updateDocument(selectedDoc.id, payload);
    setActionLoading(false);

    if (!res.success) {
      setError(res.error);
    } else {
      setSuccessMsg('Document metadata updated successfully.');
      setEditModalOpen(false);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 4000);
    }
  };

  const handleDownload = async (doc) => {
    setError(null);
    const res = await downloadDocument(doc.id, doc.original_filename);
    if (!res.success) {
      setError(res.error);
    }
  };

  const handleOpenDeleteModal = (doc) => {
    setSelectedDoc(doc);
    setError(null);
    setDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedDoc) return;
    setActionLoading(true);
    setError(null);

    const res = await deleteDocument(selectedDoc.id);
    setActionLoading(false);

    if (!res.success) {
      setError(res.error);
    } else {
      setSuccessMsg(`Document "${selectedDoc.title}" deleted.`);
      setDeleteModalOpen(false);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 4000);
    }
  };

  const uploadTypeInfo = useMemo(() => {
    return DOCUMENT_TYPES.find((t) => t.value === uploadForm.document_type);
  }, [uploadForm.document_type]);

  const editTypeInfo = useMemo(() => {
    return DOCUMENT_TYPES.find((t) => t.value === editForm.document_type);
  }, [editForm.document_type]);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white tracking-tight">Document Repository</h1>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Procurement policies, replenishment rules, vendor contracts, and supplier SLAs
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={fetchData}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium bg-white/[0.04] hover:bg-white/[0.08] text-neutral-300 border border-white/[0.08] transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
            <button
              type="button"
              onClick={handleOpenUploadModal}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-violet-500/20 transition"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Upload PDF</span>
            </button>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-start gap-3 text-xs animate-in">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
            <div className="flex-1">{error}</div>
            <button type="button" onClick={() => setError(null)} className="text-red-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {successMsg && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 flex items-center gap-3 text-xs animate-in">
            <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
            <div className="flex-1">{successMsg}</div>
            <button type="button" onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Filters Card */}
        <div className="p-4 rounded-2xl bg-neutral-900/40 border border-white/[0.06] mb-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Search */}
            <form onSubmit={handleSearchSubmit} className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
              <input
                type="text"
                placeholder="Search title or filename..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-neutral-950/60 border border-white/[0.08] text-white placeholder-neutral-500 focus:outline-none focus:border-violet-500 transition"
              />
            </form>

            {/* Type Filter */}
            <div>
              <select
                value={selectedTypeFilter}
                onChange={(e) => setSelectedTypeFilter(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/60 border border-white/[0.08] text-neutral-300 focus:outline-none focus:border-violet-500 transition"
              >
                <option value="">All Document Types</option>
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Supplier Filter */}
            <div>
              <select
                value={selectedSupplierFilter}
                onChange={(e) => setSelectedSupplierFilter(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/60 border border-white/[0.08] text-neutral-300 focus:outline-none focus:border-violet-500 transition"
              >
                <option value="">All Suppliers</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.supplier_code} — {s.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/60 border border-white/[0.08] text-neutral-300 focus:outline-none focus:border-violet-500 transition"
              >
                <option value="">All Statuses</option>
                <option value="active">Active Only</option>
                <option value="inactive">Inactive Only</option>
              </select>
            </div>
          </div>
        </div>

        {/* Documents Table */}
        <div className="rounded-2xl bg-neutral-900/40 border border-white/[0.06] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-neutral-300">
              <thead className="bg-white/[0.02] border-b border-white/[0.06] text-neutral-400 font-medium">
                <tr>
                  <th className="py-3.5 px-4">Title</th>
                  <th className="py-3.5 px-4">Type</th>
                  <th className="py-3.5 px-4">Supplier</th>
                  <th className="py-3.5 px-4">Original File</th>
                  <th className="py-3.5 px-4">File Size</th>
                  <th className="py-3.5 px-4">Uploaded</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-neutral-500">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-400" />
                      Loading document repository...
                    </td>
                  </tr>
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-neutral-500">
                      <FileText className="w-8 h-8 mx-auto mb-2 text-neutral-600 opacity-60" />
                      <p className="text-sm font-medium text-neutral-400">No documents found</p>
                      <p className="text-xs text-neutral-500 mt-1">
                        Upload procurement policies, vendor contracts, or supplier SLAs to get started.
                      </p>
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => {
                    const typeDef = DOCUMENT_TYPES.find((t) => t.value === doc.document_type);
                    return (
                      <tr key={doc.id} className="hover:bg-white/[0.02] transition">
                        <td className="py-3.5 px-4 font-medium text-white max-w-[220px] truncate" title={doc.title}>
                          {doc.title}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/10 text-violet-300 border border-violet-500/20">
                            {typeDef?.label || doc.document_type}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          {doc.supplier ? (
                            <span className="text-neutral-300 inline-flex items-center gap-1.5" title={doc.supplier.name}>
                              <Building2 className="w-3.5 h-3.5 text-neutral-500 shrink-0" />
                              <span className="font-semibold text-neutral-200">{doc.supplier.supplier_code}</span>
                            </span>
                          ) : (
                            <span className="text-neutral-500 italic">Company-wide</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 max-w-[180px] truncate font-mono text-[11px] text-neutral-400" title={doc.original_filename}>
                          {doc.original_filename}
                        </td>
                        <td className="py-3.5 px-4 text-neutral-400">
                          {formatBytes(doc.file_size_bytes)}
                        </td>
                        <td className="py-3.5 px-4 text-neutral-400">
                          {formatDate(doc.created_at)}
                        </td>
                        <td className="py-3.5 px-4">
                          {doc.is_active ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-neutral-800 text-neutral-400 border border-white/[0.06]">
                              Inactive
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleDownload(doc)}
                              className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition"
                              title="Download PDF"
                            >
                              <Download className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleOpenEditModal(doc)}
                              className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition"
                              title="Edit Metadata"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleOpenDeleteModal(doc)}
                              className="p-1.5 rounded-lg text-neutral-400 hover:text-red-400 hover:bg-red-500/[0.08] transition"
                              title="Delete Document"
                            >
                              <Trash2 className="w-4 h-4" />
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
        </div>
      </main>

      {/* Upload Modal */}
      {uploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in">
          <div className="w-full max-w-lg rounded-2xl bg-neutral-900 border border-white/[0.08] p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400">
                  <Upload className="w-4 h-4" />
                </div>
                <h2 className="text-base font-bold text-white">Upload Procurement PDF</h2>
              </div>
              <button
                type="button"
                onClick={() => setUploadModalOpen(false)}
                className="text-neutral-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4 pt-4">
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Document Title <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Master Supply Agreement 2026"
                  value={uploadForm.title}
                  onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/80 border border-white/[0.08] text-white placeholder-neutral-500 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Document Type <span className="text-red-400">*</span>
                </label>
                <select
                  value={uploadForm.document_type}
                  onChange={handleUploadTypeChange}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/80 border border-white/[0.08] text-white focus:outline-none focus:border-violet-500"
                >
                  {DOCUMENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-neutral-500 mt-1">
                  {uploadTypeInfo?.supplierRule === 'required'
                    ? '⚠️ Requires an active supplier linkage.'
                    : uploadTypeInfo?.supplierRule === 'none'
                    ? 'ℹ️ Company-wide policy document (no supplier linkage).'
                    : 'Optional supplier linkage.'}
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Supplier{' '}
                  {uploadTypeInfo?.supplierRule === 'required' ? (
                    <span className="text-red-400">*</span>
                  ) : (
                    <span className="text-neutral-500">(Optional)</span>
                  )}
                </label>
                <select
                  disabled={uploadTypeInfo?.supplierRule === 'none'}
                  required={uploadTypeInfo?.supplierRule === 'required'}
                  value={uploadForm.supplier_id}
                  onChange={(e) => setUploadForm({ ...uploadForm, supplier_id: e.target.value })}
                  className={`w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/80 border border-white/[0.08] text-white focus:outline-none focus:border-violet-500 ${
                    uploadTypeInfo?.supplierRule === 'none' ? 'opacity-40 cursor-not-allowed' : ''
                  }`}
                >
                  <option value="">
                    {uploadTypeInfo?.supplierRule === 'none' ? 'Disabled for company policies' : 'Select a Supplier...'}
                  </option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.supplier_code} — {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  PDF File <span className="text-red-400">*</span>
                </label>
                <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed border-white/[0.1] hover:border-violet-500/50 rounded-xl bg-neutral-950/40 transition cursor-pointer">
                  <div className="space-y-1 text-center">
                    <FileCheck className="mx-auto h-8 w-8 text-neutral-400" />
                    <div className="flex text-xs text-neutral-400">
                      <label className="relative cursor-pointer rounded-md font-semibold text-violet-400 hover:text-violet-300">
                        <span>Select PDF file</span>
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          onChange={handleFileChange}
                          className="sr-only"
                          required
                        />
                      </label>
                      <p className="pl-1 text-neutral-500">or drag and drop</p>
                    </div>
                    <p className="text-[10px] text-neutral-500">PDF up to 10 MB with valid %PDF- header</p>
                    {uploadFileName && (
                      <p className="text-xs font-medium text-violet-300 mt-2 font-mono">
                        Selected: {uploadFileName}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setUploadModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-neutral-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-50 transition"
                >
                  {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                  <span>{actionLoading ? 'Uploading...' : 'Confirm Upload'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Metadata Modal */}
      {editModalOpen && selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in">
          <div className="w-full max-w-lg rounded-2xl bg-neutral-900 border border-white/[0.08] p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400">
                  <Edit className="w-4 h-4" />
                </div>
                <h2 className="text-base font-bold text-white">Edit Document Metadata</h2>
              </div>
              <button
                type="button"
                onClick={() => setEditModalOpen(false)}
                className="text-neutral-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4 pt-4">
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Title</label>
                <input
                  type="text"
                  required
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/80 border border-white/[0.08] text-white focus:outline-none focus:border-violet-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">Document Type</label>
                <select
                  value={editForm.document_type}
                  onChange={handleEditTypeChange}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/80 border border-white/[0.08] text-white focus:outline-none focus:border-violet-500"
                >
                  {DOCUMENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Supplier{' '}
                  {editTypeInfo?.supplierRule === 'required' ? (
                    <span className="text-red-400">*</span>
                  ) : (
                    <span className="text-neutral-500">(Optional)</span>
                  )}
                </label>
                <select
                  disabled={editTypeInfo?.supplierRule === 'none'}
                  required={editTypeInfo?.supplierRule === 'required'}
                  value={editForm.supplier_id}
                  onChange={(e) => setEditForm({ ...editForm, supplier_id: e.target.value })}
                  className={`w-full px-3 py-2 text-xs rounded-xl bg-neutral-950/80 border border-white/[0.08] text-white focus:outline-none focus:border-violet-500 ${
                    editTypeInfo?.supplierRule === 'none' ? 'opacity-40 cursor-not-allowed' : ''
                  }`}
                >
                  <option value="">
                    {editTypeInfo?.supplierRule === 'none' ? 'Disabled for company policies' : 'None / Select Supplier'}
                  </option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.supplier_code} — {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="editIsActive"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                  className="w-4 h-4 rounded text-violet-600 bg-neutral-950 border-white/[0.1] focus:ring-violet-500"
                />
                <label htmlFor="editIsActive" className="text-xs text-neutral-300">
                  Active in repository
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-neutral-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-50 transition"
                >
                  {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Edit className="w-3.5 h-3.5" />}
                  <span>{actionLoading ? 'Saving...' : 'Save Changes'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteModalOpen && selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in">
          <div className="w-full max-w-md rounded-2xl bg-neutral-900 border border-white/[0.08] p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Delete Document</h3>
                <p className="text-xs text-neutral-400">This action will delete the database row and stored PDF file.</p>
              </div>
            </div>

            <p className="text-xs text-neutral-300 p-3 rounded-xl bg-neutral-950/60 border border-white/[0.04] mb-6">
              Are you sure you want to permanently delete{' '}
              <strong className="text-white">"{selectedDoc.title}"</strong> ({selectedDoc.original_filename})?
            </p>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setDeleteModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-neutral-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={actionLoading}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-red-600 hover:bg-red-500 text-white disabled:opacity-50 transition"
              >
                {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                <span>{actionLoading ? 'Deleting...' : 'Delete Permanently'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
