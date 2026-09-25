import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { User, Mail, Lock, CheckCircle2, AlertCircle, Loader2, ArrowRight } from 'lucide-react';
import { registerUser } from '../services/authApi';

export default function Register() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [successData, setSuccessData] = useState(null);

  const validate = () => {
    const errors = {};

    // Name validation
    if (!formData.name.trim()) {
      errors.name = 'Full name is required.';
    } else if (formData.name.trim().length > 100) {
      errors.name = 'Name cannot exceed 100 characters.';
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!formData.email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!emailRegex.test(formData.email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }

    // Password validation
    if (!formData.password) {
      errors.password = 'Password is required.';
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters long.';
    } else if (formData.password.length > 128) {
      errors.password = 'Password cannot exceed 128 characters.';
    }

    // Confirm password validation
    if (!formData.confirmPassword) {
      errors.confirmPassword = 'Please confirm your password.';
    } else if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    return errors;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    // Clear inline error on change
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({
        ...prev,
        [name]: '',
      }));
    }
    if (serverError) {
      setServerError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;

    setServerError('');
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setIsLoading(true);

    // Note: confirmPassword is strictly stripped out; only name, email, password are sent
    const result = await registerUser({
      name: formData.name,
      email: formData.email,
      password: formData.password,
    });

    setIsLoading(false);

    if (result.success) {
      setSuccessData(result.data);
    } else {
      setServerError(result.error);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col justify-between selection:bg-violet-500/30 selection:text-white">
      {/* Top Header */}
      <header className="sticky top-0 z-50 w-full">
        <div className="absolute inset-0 bg-neutral-950/70 backdrop-blur-2xl border-b border-white/[0.04]" />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
              <span className="text-white font-bold text-sm tracking-tight">S</span>
            </div>
            <div>
              <span className="text-sm font-semibold text-white tracking-tight">SmartSupply</span>
              <p className="text-[10px] text-neutral-500 leading-tight font-medium">
                Decision Support System
              </p>
            </div>
          </Link>

          <Link
            to="/"
            className="text-xs text-neutral-500 hover:text-violet-400 transition font-medium"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Main Registration Area */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 my-8">
        <div className="w-full max-w-md">
          {/* Card Container */}
          <div className="bg-neutral-900/60 border border-white/[0.06] rounded-2xl p-6 sm:p-8 shadow-xl backdrop-blur-md">
            {successData ? (
              /* Success State Screen */
              <div className="text-center py-4 space-y-4">
                <div className="w-14 h-14 bg-emerald-500/10 border border-emerald-500/20 rounded-full flex items-center justify-center mx-auto text-emerald-400">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight">
                    Account Created Successfully!
                  </h2>
                  <p className="text-sm text-neutral-300 mt-2">
                    Welcome aboard, <strong className="text-white">{successData.name}</strong>.
                    Your account has been registered with role{' '}
                    <span className="font-mono text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded text-xs">
                      user
                    </span>.
                  </p>
                </div>

                <div className="pt-4">
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-lg transition shadow-lg shadow-violet-600/25 text-sm"
                  >
                    Proceed to Log In
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              /* Registration Form */
              <div>
                <div className="mb-6">
                  <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2.5 py-0.5 rounded-full mb-2">
                    Get Started
                  </span>
                  <h2 className="text-2xl font-bold text-white tracking-tight">
                    Create your account
                  </h2>
                  <p className="text-xs text-neutral-500 mt-1">
                    Sign up to access inventory replenishment and supplier decision intelligence.
                  </p>
                </div>

                {/* Server Error Alert */}
                {serverError && (
                  <div
                    role="alert"
                    className="mb-5 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-start gap-2.5"
                  >
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <span>{serverError}</span>
                  </div>
                )}

                <form onSubmit={handleSubmit} noValidate className="space-y-4">
                  {/* Full Name */}
                  <div>
                    <label
                      htmlFor="name"
                      className="block text-xs font-medium text-neutral-400 mb-1"
                    >
                      Full Name
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-500">
                        <User className="w-4 h-4" />
                      </div>
                      <input
                        id="name"
                        name="name"
                        type="text"
                        autoComplete="name"
                        value={formData.name}
                        onChange={handleChange}
                        disabled={isLoading}
                        placeholder="John Silva"
                        className={`w-full pl-9 pr-3 py-2 bg-neutral-900 border rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-1 transition ${
                          fieldErrors.name
                            ? 'border-red-500/50 focus:border-red-500 focus:ring-red-500/20'
                            : 'border-white/[0.08] focus:border-violet-500 focus:ring-violet-500/20'
                        }`}
                      />
                    </div>
                    {fieldErrors.name && (
                      <p className="text-[11px] text-red-400 mt-1">{fieldErrors.name}</p>
                    )}
                  </div>

                  {/* Email */}
                  <div>
                    <label
                      htmlFor="email"
                      className="block text-xs font-medium text-neutral-400 mb-1"
                    >
                      Work Email
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-500">
                        <Mail className="w-4 h-4" />
                      </div>
                      <input
                        id="email"
                        name="email"
                        type="email"
                        autoComplete="email"
                        value={formData.email}
                        onChange={handleChange}
                        disabled={isLoading}
                        placeholder="john@example.com"
                        className={`w-full pl-9 pr-3 py-2 bg-neutral-900 border rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-1 transition ${
                          fieldErrors.email
                            ? 'border-red-500/50 focus:border-red-500 focus:ring-red-500/20'
                            : 'border-white/[0.08] focus:border-violet-500 focus:ring-violet-500/20'
                        }`}
                      />
                    </div>
                    {fieldErrors.email && (
                      <p className="text-[11px] text-red-400 mt-1">{fieldErrors.email}</p>
                    )}
                  </div>

                  {/* Password */}
                  <div>
                    <label
                      htmlFor="password"
                      className="block text-xs font-medium text-neutral-400 mb-1"
                    >
                      Password
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-500">
                        <Lock className="w-4 h-4" />
                      </div>
                      <input
                        id="password"
                        name="password"
                        type="password"
                        autoComplete="new-password"
                        value={formData.password}
                        onChange={handleChange}
                        disabled={isLoading}
                        placeholder="Minimum 8 characters"
                        className={`w-full pl-9 pr-3 py-2 bg-neutral-900 border rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-1 transition ${
                          fieldErrors.password
                            ? 'border-red-500/50 focus:border-red-500 focus:ring-red-500/20'
                            : 'border-white/[0.08] focus:border-violet-500 focus:ring-violet-500/20'
                        }`}
                      />
                    </div>
                    {fieldErrors.password && (
                      <p className="text-[11px] text-red-400 mt-1">{fieldErrors.password}</p>
                    )}
                  </div>

                  {/* Confirm Password */}
                  <div>
                    <label
                      htmlFor="confirmPassword"
                      className="block text-xs font-medium text-neutral-400 mb-1"
                    >
                      Confirm Password
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-500">
                        <Lock className="w-4 h-4" />
                      </div>
                      <input
                        id="confirmPassword"
                        name="confirmPassword"
                        type="password"
                        autoComplete="new-password"
                        value={formData.confirmPassword}
                        onChange={handleChange}
                        disabled={isLoading}
                        placeholder="Re-enter password"
                        className={`w-full pl-9 pr-3 py-2 bg-neutral-900 border rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-1 transition ${
                          fieldErrors.confirmPassword
                            ? 'border-red-500/50 focus:border-red-500 focus:ring-red-500/20'
                            : 'border-white/[0.08] focus:border-violet-500 focus:ring-violet-500/20'
                        }`}
                      />
                    </div>
                    {fieldErrors.confirmPassword && (
                      <p className="text-[11px] text-red-400 mt-1">
                        {fieldErrors.confirmPassword}
                      </p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <div className="pt-2">
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium rounded-lg transition shadow-lg shadow-violet-600/25 text-sm"
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Creating account...</span>
                        </>
                      ) : (
                        <span>Create Account</span>
                      )}
                    </button>
                  </div>
                </form>

                {/* Footer Navigation */}
                <div className="mt-6 pt-4 border-t border-white/[0.04] text-center text-xs text-neutral-500">
                  Already have an account?{' '}
                  <Link
                    to="/login"
                    className="text-violet-400 hover:text-violet-300 font-medium transition"
                  >
                    Log in
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Page Footer */}
      <footer className="border-t border-white/[0.04] py-4 text-center text-xs text-neutral-600">
        SmartSupply AI • Inventory Replenishment & Supplier Decision Support System
      </footer>
    </div>
  );
}
