import React from 'react';
import { Link } from 'react-router-dom';
import { Layers, Lock, ArrowLeft } from 'lucide-react';

export default function Login() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition">
            <div className="p-2 bg-sky-500/10 border border-sky-500/30 rounded-lg">
              <Layers className="w-5 h-5 text-sky-400" />
            </div>
            <div>
              <span className="text-sm font-semibold text-white tracking-tight">
                SmartSupply AI
              </span>
              <p className="text-[11px] text-slate-400 font-mono">
                Decision Support System
              </p>
            </div>
          </Link>
          <Link
            to="/"
            className="text-xs text-slate-400 hover:text-sky-400 transition font-medium"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 my-8">
        <div className="w-full max-w-md bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center backdrop-blur-md shadow-xl">
          <div className="w-12 h-12 bg-sky-500/10 border border-sky-500/30 rounded-full flex items-center justify-center mx-auto text-sky-400 mb-4">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Sign In to SmartSupply AI
          </h2>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            The login user interface is scheduled for deployment in the next milestone. If you just registered an account, your credentials are saved in the system.
          </p>
          <div className="mt-6 flex flex-col gap-2.5">
            <Link
              to="/register"
              className="py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-lg text-xs transition border border-slate-700"
            >
              Back to Registration
            </Link>
            <Link
              to="/"
              className="py-2.5 px-4 bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold rounded-lg text-xs transition shadow-lg shadow-sky-500/20"
            >
              View System Status Dashboard
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        SmartSupply AI • Inventory Replenishment & Supplier Decision Support System
      </footer>
    </div>
  );
}
