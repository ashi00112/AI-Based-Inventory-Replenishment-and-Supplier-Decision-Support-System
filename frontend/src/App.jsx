import React from 'react';
import SystemStatus from './components/SystemStatus';
import { Layers, GitBranch, BookOpen, Terminal } from 'lucide-react';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-sky-500/10 border border-sky-500/30 rounded-lg">
              <Layers className="w-5 h-5 text-sky-400" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white tracking-tight">
                AI Inventory & Supplier DSS
              </h1>
              <p className="text-[11px] text-slate-400 font-mono">
                Common Foundation • 4-Developer Monorepo
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono">
              FastAPI + React + Supabase Postgres
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Banner */}
        <section className="bg-gradient-to-r from-sky-950/40 via-slate-900 to-slate-900/80 border border-sky-900/30 rounded-2xl p-6 sm:p-8">
          <div className="max-w-2xl">
            <span className="inline-block text-xs font-semibold uppercase tracking-wider text-sky-400 bg-sky-950/60 px-2.5 py-1 rounded-full border border-sky-800/40 mb-3">
              Phase 1: Shared Project Scaffold
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              AI-Based Inventory Replenishment & Supplier Decision Support System
            </h2>
            <p className="text-sm text-slate-300 mt-2 leading-relaxed">
              Shared development foundation for our 4-member engineering team. Backend services, database migration pipeline, and frontend dashboard are configured and ready for feature branching.
            </p>
          </div>
        </section>

        {/* Live System & Agent Workspaces */}
        <SystemStatus />

        {/* Developer Quick Reference Guide */}
        <section className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-6">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 mb-4">
            <Terminal className="w-4 h-4 text-sky-400" />
            Quick Reference Commands for Team Members
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/60">
              <span className="text-slate-400 block mb-2 font-sans font-semibold">1. Connect Supabase DB</span>
              <p className="text-sky-300">Set DATABASE_URL in backend/.env</p>
            </div>
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/60">
              <span className="text-slate-400 block mb-2 font-sans font-semibold">2. Backend Dev Server</span>
              <p className="text-sky-300">uvicorn app.main:app --reload --port 8000</p>
            </div>
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/60">
              <span className="text-slate-400 block mb-2 font-sans font-semibold">3. Apply DB Migrations</span>
              <p className="text-sky-300">alembic upgrade head</p>
            </div>
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/60">
              <span className="text-slate-400 block mb-2 font-sans font-semibold">4. Run Backend Tests</span>
              <p className="text-sky-300">pytest</p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 mt-12 py-6 text-center text-xs text-slate-500">
        AI-Based Inventory Replenishment and Supplier Decision Support System • University Group Project
      </footer>
    </div>
  );
}
