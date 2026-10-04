import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, AlertCircle, Loader2, LogIn, ShieldCheck, Cpu, ArrowRight, CheckCircle2 } from 'lucide-react';
import { loginUser } from '../services/authApi';
import { setAccessToken } from '../services/tokenStorage';
import { useAuth } from '../context/AuthContext';
import AnimatedBrand from '../components/AnimatedBrand';

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
      setAccessToken(result.data.access_token);
      await refreshCurrentUser();
      navigate('/');
    } else {
      setServerError(result.error);
      setFormData((prev) => ({ ...prev, password: '' }));
    }
  };

  return (
    <div className="min-h-screen bg-[#01272e] text-[#EAF4F4] flex flex-col justify-between font-sans selection:bg-[#03D26F]/30 selection:text-white">
      {/* Top Bar */}
      <header className="sticky top-0 z-50 w-full bg-[#01353e]/80 backdrop-blur-xl border-b border-white/[0.08]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="group flex items-center">
            <AnimatedBrand size="sm" subtitle="Decision Support System" />
          </Link>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-block text-[11px] font-mono uppercase tracking-wider text-[#CEF431] bg-[#CEF431]/10 px-2.5 py-1 rounded-full border border-[#CEF431]/20">
              Enterprise v2.0
            </span>
          </div>
        </div>
      </header>

      {/* Main Content — Split Screen Layout */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-10 my-auto">
        <div className="w-full max-w-5xl rounded-3xl bg-[#01353e]/60 border border-white/[0.1] shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12 backdrop-blur-xl">
          
          {/* Left Hero Brand Panel (5 cols on lg) */}
          <div className="relative lg:col-span-6 bg-[#014651] p-8 sm:p-10 flex flex-col justify-between overflow-hidden">
            {/* Background Hero Image with Cyprus Duotone Gradient Overlay */}
            <div
              className="absolute inset-0 bg-cover bg-center opacity-40 mix-blend-luminosity scale-105"
              style={{ backgroundImage: `url('/assets/login-hero.jpg')` }}
            />
            <div className="absolute inset-0 bg-gradient-to-tr from-[#01272e] via-[#014651]/90 to-[#025866]/80" />
            
            {/* Top Badge */}
            <div className="relative z-10 space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#03D26F]/15 border border-[#03D26F]/30 text-[#03D26F] text-xs font-semibold">
                <Cpu className="w-3.5 h-3.5" />
                <span>Autonomous Supply Chain AI</span>
              </div>

              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black text-white tracking-tight leading-tight">
                Smarter Supply Decisions. <br />
                <span className="text-[#03D26F]">Powered by AI.</span>
              </h1>

              <p className="text-xs sm:text-sm text-[#EAF4F4]/80 leading-relaxed max-w-md">
                Unifying physical inventory status, probabilistic demand risk, and real-time supplier SLA contracts into verified replenishment directives.
              </p>
            </div>

            {/* Feature Bullets */}
            <div className="relative z-10 my-8 space-y-3.5">
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-[#03D26F]/20 text-[#03D26F] flex items-center justify-center shrink-0 mt-0.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs text-[#EAF4F4]/90">
                  <strong className="text-white block font-semibold">4-Agent Autonomous Synthesis</strong>
                  Multi-agent consensus ensures resilient stock forecasts.
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-[#CEF431]/20 text-[#CEF431] flex items-center justify-center shrink-0 mt-0.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs text-[#EAF4F4]/90">
                  <strong className="text-white block font-semibold">Grok LLM Explainability</strong>
                  Audit-ready reasoning for every unit order recommendation.
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-[#03D26F]/20 text-[#03D26F] flex items-center justify-center shrink-0 mt-0.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs text-[#EAF4F4]/90">
                  <strong className="text-white block font-semibold">Enterprise RBAC Enforced</strong>
                  Human-in-the-loop review protects procurement budgets.
                </div>
              </div>
            </div>

            {/* Bottom System Status */}
            <div className="relative z-10 pt-4 border-t border-white/[0.1] flex items-center justify-between text-[11px] text-[#EAF4F4]/60 font-mono">
              <span>Cluster: Production-Alpha</span>
              <span className="flex items-center gap-1.5 text-[#03D26F]">
                <span className="w-2 h-2 rounded-full bg-[#03D26F] animate-pulse" />
                Operational
              </span>
            </div>
          </div>

          {/* Right Form Panel (6 cols on lg) */}
          <div className="lg:col-span-6 bg-[#01353e]/90 p-8 sm:p-10 flex flex-col justify-center">
            <div className="max-w-md w-full mx-auto space-y-6">
              <div>
                <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-[#03D26F] bg-[#03D26F]/10 border border-[#03D26F]/20 px-2.5 py-0.5 rounded-full mb-2">
                  Secure Workspace Access
                </span>
                <h2 className="text-2xl font-bold text-white tracking-tight">
                  Sign in to your account
                </h2>
                <p className="text-xs text-[#EAF4F4]/70 mt-1">
                  Enter your enterprise credentials to access replenishment and supplier decision workflows.
                </p>
              </div>

              {/* Server Error Alert */}
              {serverError && (
                <div
                  role="alert"
                  className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-start gap-2.5 animate-in"
                >
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <span>{serverError}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate className="space-y-4">
                {/* Email Field */}
                <div>
                  <label
                    htmlFor="email"
                    className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1.5"
                  >
                    Corporate Email Address
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#EAF4F4]/40">
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
                      placeholder="admin@smartsupply.ai"
                      className={`w-full pl-10 pr-3.5 py-2.5 bg-[#01272e]/80 border rounded-xl text-sm text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:ring-2 transition ${
                        fieldErrors.email
                          ? 'border-rose-500 focus:ring-rose-500/25'
                          : 'border-white/[0.1] focus:border-[#03D26F] focus:ring-[#03D26F]/20'
                      }`}
                    />
                  </div>
                  {fieldErrors.email && (
                    <p className="text-[11px] text-rose-400 mt-1">{fieldErrors.email}</p>
                  )}
                </div>

                {/* Password Field */}
                <div>
                  <label
                    htmlFor="password"
                    className="block text-xs font-semibold text-[#EAF4F4]/80 mb-1.5"
                  >
                    Account Password
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#EAF4F4]/40">
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
                      placeholder="••••••••••••"
                      className={`w-full pl-10 pr-3.5 py-2.5 bg-[#01272e]/80 border rounded-xl text-sm text-white placeholder-[#EAF4F4]/30 focus:outline-none focus:ring-2 transition ${
                        fieldErrors.password
                          ? 'border-rose-500 focus:ring-rose-500/25'
                          : 'border-white/[0.1] focus:border-[#03D26F] focus:ring-[#03D26F]/20'
                      }`}
                    />
                  </div>
                  {fieldErrors.password && (
                    <p className="text-[11px] text-rose-400 mt-1">{fieldErrors.password}</p>
                  )}
                </div>

                {/* Submit CTA — Malachite Green Button */}
                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-[#03D26F] hover:bg-[#02be63] disabled:opacity-50 disabled:cursor-not-allowed text-[#161514] font-bold rounded-xl transition shadow-lg shadow-[#03D26F]/25 text-sm cursor-pointer"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-[#161514]" />
                        <span>Authenticating Workspace...</span>
                      </>
                    ) : (
                      <>
                        <LogIn className="w-4 h-4 text-[#161514]" />
                        <span>Sign In to System</span>
                      </>
                    )}
                  </button>
                </div>
              </form>

              {/* Internal System Footer Notice */}
              <div className="pt-4 border-t border-white/[0.08] text-center space-y-1">
                <div className="inline-flex items-center gap-1.5 text-xs text-[#EAF4F4]/80 font-medium">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#03D26F]" />
                  <span>Internal Enterprise System</span>
                </div>
                <p className="text-[11px] text-[#EAF4F4]/50 leading-relaxed">
                  Public self-registration is disabled. Staff accounts are provisioned exclusively by system administrators.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] py-4 text-center text-xs text-[#EAF4F4]/50 bg-[#01272e]">
        SmartSupply AI • Autonomous Inventory Replenishment & Supplier Decision Support System
      </footer>
    </div>
  );
}

