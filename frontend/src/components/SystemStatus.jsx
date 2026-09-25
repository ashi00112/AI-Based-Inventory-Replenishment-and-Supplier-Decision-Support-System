import React, { useEffect, useState } from 'react';
import { fetchHealthStatus, API_BASE_URL } from '../services/api';
import { 
  Server, 
  Database, 
  Activity, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Boxes, 
  TrendingUp, 
  Truck, 
  BrainCircuit, 
  ExternalLink 
} from 'lucide-react';

export default function SystemStatus() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState(null);

  const checkHealth = async () => {
    setLoading(true);
    const result = await fetchHealthStatus();
    setHealth(result);
    setLastChecked(new Date().toLocaleTimeString());
    setLoading(false);
  };

  useEffect(() => {
    checkHealth();
    const timer = setInterval(checkHealth, 15000);
    return () => clearInterval(timer);
  }, []);

  const agents = [
    {
      id: 1,
      name: 'Inventory Monitoring Agent',
      developer: 'Developer 1',
      dir: 'backend/app/agents/inventory/',
      status: 'Ready for Development',
      icon: Boxes,
      color: 'text-violet-400 border-violet-500/20 bg-violet-500/10',
    },
    {
      id: 2,
      name: 'Demand & Risk Analysis Agent',
      developer: 'Developer 2',
      dir: 'backend/app/agents/demand/',
      status: 'Ready for Development',
      icon: TrendingUp,
      color: 'text-teal-400 border-teal-500/20 bg-teal-500/10',
    },
    {
      id: 3,
      name: 'Supplier Intelligence Agent',
      developer: 'Developer 3',
      dir: 'backend/app/agents/supplier/',
      status: 'Ready for Development',
      icon: Truck,
      color: 'text-amber-400 border-amber-500/20 bg-amber-500/10',
    },
    {
      id: 4,
      name: 'Replenishment Decision Agent',
      developer: 'Developer 4',
      dir: 'backend/app/agents/decision/',
      status: 'Ready for Development',
      icon: BrainCircuit,
      color: 'text-indigo-400 border-indigo-500/20 bg-indigo-500/10',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Health Monitoring Bar */}
      <div className="bg-neutral-900/60 border border-white/[0.06] rounded-2xl p-6 backdrop-blur-md shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.04]">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-violet-400" />
              Core Infrastructure Health
            </h2>
            <p className="text-xs text-neutral-400 mt-1">
              Live heartbeat and database connectivity probe connected to <code className="text-violet-300 text-[11px] bg-neutral-800/80 px-2 py-0.5 rounded font-mono">{API_BASE_URL}</code>
            </p>
          </div>
          <button
            onClick={checkHealth}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.05] hover:bg-white/[0.08] text-neutral-200 border border-white/[0.06] transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 pt-6">
          {/* FastAPI Card */}
          <div className="bg-neutral-950/60 border border-white/[0.04] rounded-xl p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-neutral-400 flex items-center gap-2">
                <Server className="w-3.5 h-3.5 text-neutral-400" />
                FastAPI Backend
              </span>
              {health?.success ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  <CheckCircle2 className="w-3 h-3" /> Online
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full border border-red-500/20">
                  <AlertCircle className="w-3 h-3" /> Unreachable
                </span>
              )}
            </div>
            <p className="text-xs text-neutral-400 mt-2">
              Endpoint: <span className="text-neutral-300 font-mono">/health</span>
            </p>
            {health?.data && (
              <p className="text-xs text-neutral-400 mt-1">
                Env: <span className="text-neutral-300 font-mono">{health.data.environment}</span>
              </p>
            )}
          </div>

          {/* PostgreSQL Card */}
          <div className="bg-neutral-950/60 border border-white/[0.04] rounded-xl p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-neutral-400 flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-neutral-400" />
                Supabase PostgreSQL
              </span>
              {health?.success && health?.data?.database_connected ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  <CheckCircle2 className="w-3 h-3" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                  <AlertCircle className="w-3 h-3" /> Awaiting Supabase
                </span>
              )}
            </div>
            <p className="text-xs text-neutral-400 mt-2">
              Latency: <span className="text-neutral-300 font-mono">{health?.data?.database_latency_ms ? `${health.data.database_latency_ms} ms` : 'N/A'}</span>
            </p>
            <p className="text-xs text-neutral-400 mt-1">
              Engine: <span className="text-neutral-300 font-mono">SQLAlchemy 2.0 (Psycopg 3)</span>
            </p>
          </div>

          {/* API Documentation */}
          <div className="bg-neutral-950/60 border border-white/[0.04] rounded-xl p-4 flex flex-col justify-between">
            <div>
              <span className="text-xs font-medium text-neutral-400">
                Swagger Docs
              </span>
              <p className="text-xs text-neutral-500 mt-1">
                Interactive OpenAPI interface for testing backend routes.
              </p>
            </div>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 font-medium mt-3"
            >
              Open Swagger UI <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {lastChecked && (
          <p className="text-[10px] text-neutral-600 mt-4 text-right">
            Last polled at: {lastChecked}
          </p>
        )}
      </div>

      {/* 4 Agent Workspaces Overview */}
      <div>
        <div className="mb-4">
          <h2 className="text-base font-semibold text-white">
            Team Agent Architecture (4 Assigned Modules)
          </h2>
          <p className="text-xs text-neutral-500">
            Dedicated scaffold directories created for each member to work concurrently without merge conflicts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                className="bg-neutral-900/60 border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.12] transition"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg border ${agent.color}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-medium text-neutral-200 text-sm">
                        {agent.name}
                      </h3>
                      <span className="text-xs text-neutral-500 font-mono">
                        {agent.developer}
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-white/[0.05] text-neutral-400 border border-white/[0.06]">
                    {agent.status}
                  </span>
                </div>

                <div className="mt-4 pt-3 border-t border-white/[0.04]">
                  <p className="text-[11px] text-neutral-500">
                    Directory: <code className="text-neutral-300 font-mono bg-neutral-950 px-1.5 py-0.5 rounded text-[10px]">{agent.dir}</code>
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
