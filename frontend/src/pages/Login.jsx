import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, AlertCircle, Loader2, LogIn } from 'lucide-react';
import { loginUser } from '../services/authApi';
import { setAccessToken } from '../services/tokenStorage';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { refreshCurrentUser } = useAuth();


  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const validate = () => {
    const errors = {};

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

    const result = await loginUser({
      email: formData.email,
      password: formData.password,
    });

    setIsLoading(false);

    if (result.success) {
      // Store token via centralized utility — never log the token
      setAccessToken(result.data.access_token);
      // Request/load current user and update auth context
      await refreshCurrentUser();
      // Navigate to main dashboard
      navigate('/');
    } else {
      setServerError(result.error);
      // Clear password on authentication failure for security
      setFormData((prev) => ({ ...prev, password: '' }));
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col justify-between">
      {/* Header */}
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

      {/* Main Login Area */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 my-8">
        <div className="w-full max-w-md">
          {/* Card Container */}
          <div className="bg-neutral-900/60 border border-white/[0.06] rounded-2xl p-6 sm:p-8 shadow-xl backdrop-blur-md">
            <div className="mb-6">
              <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2.5 py-0.5 rounded-full mb-2">
                Welcome Back
              </span>
              <h2 className="text-2xl font-bold text-white tracking-tight">
                Sign in to your account
              </h2>
              <p className="text-xs text-neutral-500 mt-1">
                Access your inventory replenishment and supplier decision intelligence dashboard.
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
              {/* Email */}
              <div>
                <label
                  htmlFor="email"
                  className="block text-xs font-medium text-neutral-400 mb-1"
                >
                  Email Address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-600">
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
                    className={`w-full pl-9 pr-3 py-2 bg-neutral-950/80 border rounded-lg text-sm text-white placeholder-neutral-600 focus:outline-none focus:ring-2 transition ${
                      fieldErrors.email
                        ? 'border-red-500 focus:ring-red-500/20'
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
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-600">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={formData.password}
                    onChange={handleChange}
                    disabled={isLoading}
                    placeholder="Enter your password"
                    className={`w-full pl-9 pr-3 py-2 bg-neutral-950/80 border rounded-lg text-sm text-white placeholder-neutral-600 focus:outline-none focus:ring-2 transition ${
                      fieldErrors.password
                        ? 'border-red-500 focus:ring-red-500/20'
                        : 'border-white/[0.08] focus:border-violet-500 focus:ring-violet-500/20'
                    }`}
                  />
                </div>
                {fieldErrors.password && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.password}</p>
                )}
              </div>

              {/* Submit Button */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition shadow-lg shadow-violet-600/20 text-sm"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Signing in...</span>
                    </>
                  ) : (
                    <>
                      <LogIn className="w-4 h-4" />
                      <span>Sign In</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Footer Navigation */}
            <div className="mt-6 pt-4 border-t border-white/[0.06] text-center text-xs text-neutral-500">
              Don&apos;t have an account?{' '}
              <Link
                to="/register"
                className="text-violet-400 hover:text-violet-300 font-medium transition"
              >
                Create one
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.04] py-4 text-center text-xs text-neutral-600">
        SmartSupply AI • Inventory Replenishment & Supplier Decision Support System
      </footer>
    </div>
  );
}
