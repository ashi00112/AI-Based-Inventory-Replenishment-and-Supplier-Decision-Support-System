import React, { useState, useEffect, useCallback } from 'react';
import {
  Users as UsersIcon,
  UserPlus,
  Shield,
  UserCheck,
  UserX,
  Mail,
  Lock,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  X,
  Clock,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import { useAuth } from '../context/AuthContext';
import {
  getUsers,
  createUser,
  deactivateUser,
  activateUser,
} from '../services/userApi';

export default function Users() {
  const { user: currentUser } = useAuth();

  // User list state
  const [users, setUsers] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');

  // Create User Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: 'STAFF',
  });
  const [formErrors, setFormErrors] = useState({});
  const [formServerError, setFormServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Status Action state
  const [actionInProgressId, setActionInProgressId] = useState(null);
  const [bannerMessage, setBannerMessage] = useState(null);

  // Fetch users from API
  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    const params = { limit: 100 };
    if (roleFilter) params.role = roleFilter;
    if (activeFilter !== '') params.isActive = activeFilter === 'true';

    const res = await getUsers(params);
    if (res.success && res.data) {
      setUsers(res.data.items || []);
      setTotalCount(res.data.total || 0);
    } else {
      setBannerMessage({ type: 'error', text: res.error || 'Failed to load user accounts.' });
    }
    setIsLoading(false);
  }, [roleFilter, activeFilter]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Client-side search filtering
  const filteredUsers = users.filter((u) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      (u.name && u.name.toLowerCase().includes(query)) ||
      (u.email && u.email.toLowerCase().includes(query)) ||
      (u.role && u.role.toLowerCase().includes(query))
    );
  });

  // Modal form validation
  const validateForm = () => {
    const errors = {};
    if (!formData.name.trim()) errors.name = 'Full name is required.';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!formData.email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!emailRegex.test(formData.email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }
    if (!formData.password) {
      errors.password = 'Password is required.';
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters long.';
    }
    return errors;
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (formErrors[name]) {
      setFormErrors((prev) => ({ ...prev, [name]: '' }));
    }
    if (formServerError) setFormServerError('');
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setFormServerError('');
    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setIsSubmitting(true);
    const res = await createUser({
      name: formData.name,
      email: formData.email,
      password: formData.password,
      role: formData.role,
    });
    setIsSubmitting(false);

    if (res.success) {
      setIsModalOpen(false);
      setFormData({ name: '', email: '', password: '', role: 'STAFF' });
      setBannerMessage({
        type: 'success',
        text: `Account for ${res.data.name} (${res.data.role.toUpperCase()}) created successfully.`,
      });
      loadUsers();
    } else {
      setFormServerError(res.error || 'Failed to create user account.');
    }
  };

  const handleToggleActive = async (targetUser) => {
    if (targetUser.id === currentUser?.id) {
      alert('You cannot deactivate your own active session.');
      return;
    }

    setActionInProgressId(targetUser.id);
    const action = targetUser.is_active ? deactivateUser : activateUser;
    const res = await action(targetUser.id);
    setActionInProgressId(null);

    if (res.success) {
      setBannerMessage({
        type: 'success',
        text: `User ${targetUser.name} has been ${targetUser.is_active ? 'deactivated' : 'reactivated'}.`,
      });
      loadUsers();
    } else {
      setBannerMessage({
        type: 'error',
        text: res.error || 'Action failed.',
      });
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Banner Alert if any */}
        {bannerMessage && (
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs ${
              bannerMessage.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
            }`}
          >
            <div className="flex items-center gap-2">
              {bannerMessage.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
              )}
              <span>{bannerMessage.text}</span>
            </div>
            <button
              onClick={() => setBannerMessage(null)}
              className="text-neutral-400 hover:text-white transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2.5 py-0.5 rounded-full">
                <Shield className="w-3 h-3" /> Admin Only
              </span>
              <span className="text-xs text-neutral-500">Internal Company Directory</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
              User Management
            </h1>
            <p className="text-xs text-neutral-400 mt-0.5">
              Provision internal staff accounts and manage system role permissions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-lg shadow-violet-600/20 transition"
            >
              <UserPlus className="w-4 h-4" />
              <span>Create Staff User</span>
            </button>
          </div>
        </div>

        {/* Controls & Filter Bar */}
        <div className="bg-neutral-900/40 border border-white/[0.06] rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, email, role..."
              className="w-full bg-neutral-950/80 border border-white/[0.08] rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-violet-500/50"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="bg-neutral-950/80 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-neutral-300 focus:outline-none"
            >
              <option value="">All Roles</option>
              <option value="ADMIN">Admin</option>
              <option value="STAFF">Staff</option>
            </select>

            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="bg-neutral-950/80 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-neutral-300 focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Inactive Only</option>
            </select>

            <button
              onClick={loadUsers}
              className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-neutral-400 hover:text-white transition"
              title="Refresh list"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-violet-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* Users Table */}
        <div className="rounded-2xl border border-white/[0.06] bg-neutral-900/40 backdrop-blur-xl overflow-hidden">
          {isLoading && users.length === 0 ? (
            <div className="p-12 text-center text-xs text-neutral-500 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-violet-400" />
              <span>Loading user directory...</span>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="p-12 text-center text-xs text-neutral-500">
              No matching user accounts found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/[0.06] bg-white/[0.02] text-neutral-400 uppercase tracking-wider font-semibold text-[10px]">
                  <tr>
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-4">Email</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4">Account Status</th>
                    <th className="py-3 px-4">Created Date</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {filteredUsers.map((u) => {
                    const isSelf = u.id === currentUser?.id;
                    const isStaffRole = (u.role || '').toLowerCase() === 'staff' || (u.role || '').toLowerCase() === 'user';
                    const roleUpper = isStaffRole ? 'STAFF' : 'ADMIN';

                    return (
                      <tr key={u.id} className="hover:bg-white/[0.02] transition">
                        {/* Name + Avatar */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center font-bold text-white text-xs flex-shrink-0">
                              {u.name?.charAt(0)?.toUpperCase() || 'U'}
                            </div>
                            <div>
                              <div className="font-medium text-white flex items-center gap-1.5">
                                <span>{u.name}</span>
                                {isSelf && (
                                  <span className="text-[9px] font-semibold text-teal-400 bg-teal-500/10 px-1.5 py-0.2 rounded-full border border-teal-500/20">
                                    You
                                  </span>
                                )}
                              </div>
                              <span className="text-[10px] text-neutral-500 font-mono">ID #{u.id}</span>
                            </div>
                          </div>
                        </td>

                        {/* Email */}
                        <td className="py-3.5 px-4 font-mono text-neutral-300">
                          {u.email}
                        </td>

                        {/* Role */}
                        <td className="py-3.5 px-4">
                          {roleUpper === 'ADMIN' ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300 border border-violet-500/30">
                              <Shield className="w-3 h-3 text-violet-400" /> ADMIN
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-500/15 text-slate-300 border border-slate-500/30">
                              <UsersIcon className="w-3 h-3 text-slate-400" /> STAFF
                            </span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-4">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <UserCheck className="w-3 h-3" /> Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                              <UserX className="w-3 h-3" /> Inactive
                            </span>
                          )}
                        </td>

                        {/* Created Date */}
                        <td className="py-3.5 px-4 text-neutral-400 text-[11px]">
                          {formatDate(u.created_at)}
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 text-right">
                          {isSelf ? (
                            <span className="text-[11px] text-neutral-600 italic">Protected</span>
                          ) : (
                            <button
                              type="button"
                              disabled={actionInProgressId === u.id}
                              onClick={() => handleToggleActive(u)}
                              className={`px-3 py-1 rounded-lg text-xs font-medium transition disabled:opacity-50 inline-flex items-center gap-1 ${
                                u.is_active
                                  ? 'bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20'
                                  : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/20'
                              }`}
                            >
                              {actionInProgressId === u.id ? (
                                <RefreshCw className="w-3 h-3 animate-spin" />
                              ) : u.is_active ? (
                                <>
                                  <UserX className="w-3 h-3" />
                                  <span>Deactivate</span>
                                </>
                              ) : (
                                <>
                                  <UserCheck className="w-3 h-3" />
                                  <span>Reactivate</span>
                                </>
                              )}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Create User Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm">
          <div className="max-w-md w-full rounded-2xl bg-neutral-900 border border-white/[0.08] p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <UserPlus className="w-4 h-4 text-violet-400" /> Create Internal User
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5">
                  Provision an internal Staff or Administrator account.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-neutral-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {formServerError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{formServerError}</span>
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-neutral-300 font-medium mb-1">Full Name</label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="e.g. Priyantha Fernando"
                  className={`w-full bg-neutral-950 border ${
                    formErrors.name ? 'border-rose-500' : 'border-white/[0.08]'
                  } rounded-xl px-3 py-2 text-white focus:outline-none focus:border-violet-500/50`}
                />
                {formErrors.name && (
                  <p className="text-rose-400 text-[11px] mt-1">{formErrors.name}</p>
                )}
              </div>

              <div>
                <label className="block text-neutral-300 font-medium mb-1">Company Email</label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  placeholder="e.g. p.fernando@smartsupply.com"
                  className={`w-full bg-neutral-950 border ${
                    formErrors.email ? 'border-rose-500' : 'border-white/[0.08]'
                  } rounded-xl px-3 py-2 text-white focus:outline-none focus:border-violet-500/50`}
                />
                {formErrors.email && (
                  <p className="text-rose-400 text-[11px] mt-1">{formErrors.email}</p>
                )}
              </div>

              <div>
                <label className="block text-neutral-300 font-medium mb-1">Temporary Password</label>
                <input
                  type="password"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Min 8 characters (e.g. Temporary123!)"
                  className={`w-full bg-neutral-950 border ${
                    formErrors.password ? 'border-rose-500' : 'border-white/[0.08]'
                  } rounded-xl px-3 py-2 text-white focus:outline-none focus:border-violet-500/50`}
                />
                {formErrors.password && (
                  <p className="text-rose-400 text-[11px] mt-1">{formErrors.password}</p>
                )}
              </div>

              <div>
                <label className="block text-neutral-300 font-medium mb-1">System Role</label>
                <select
                  name="role"
                  value={formData.role}
                  onChange={handleInputChange}
                  className="w-full bg-neutral-950 border border-white/[0.08] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-violet-500/50"
                >
                  <option value="STAFF">STAFF (Catalog, Inventory & Decision Generation)</option>
                  <option value="ADMIN">ADMIN (Full Privileges & Decision Approval)</option>
                </select>
                <p className="text-[10px] text-neutral-500 mt-1">
                  STAFF users cannot approve/reject decisions or manage other accounts.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-lg shadow-violet-600/20 transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <UserPlus className="w-3.5 h-3.5" />
                      <span>Create Account</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
