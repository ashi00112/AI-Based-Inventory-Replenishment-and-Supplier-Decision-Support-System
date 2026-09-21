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
      color: 'text-sky-400 border-sky-500/30 bg-sky-950/20',
    },
    {
      id: 2,
      name: 'Demand & Risk Analysis Agent',
      developer: 'Developer 2',
      dir: 'backend/app/agents/demand/',
      status: 'Ready for Development',
      icon: TrendingUp,
      color: 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20',
    },
    {
      id: 3,
      name: 'Supplier Intelligence Agent',
      developer: 'Developer 3',
      dir: 'backend/app/agents/supplier/',
      status: 'Ready for Development',
      icon: Truck,
      color: 'text-amber-400 border-amber-500/30 bg-amber-950/20',
    },
    {
      id: 4,
      name: 'Replenishment Decision Agent',
      developer: 'Developer 4',
      dir: 'backend/app/agents/decision/',
      status: 'Ready for Development',
      icon: BrainCircuit,
      color: 'text-purple-400 border-purple-500/30 bg-purple-950/20',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Top Health Monitoring Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 backdrop-blur-md shadow-xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-sky-400" />
              Core Infrastructure Health
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Live heartbeat and database connectivity probe connected to <code className="text-sky-300 text-xs bg-slate-800 px-2 py-0.5 rounded">{API_BASE_URL}</code>
            </p>
          </div>
          <button
            onClick={checkHealth}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6">
          {/* FastAPI Card */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center gap-2">
                <Server className="w-4 h-4 text-slate-400" />
                FastAPI Backend
              </span>
              {health?.success ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded-full border border-emerald-800/40">
                  <CheckCircle2 className="w-3 h-3" /> Online
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-400 bg-rose-950/50 px-2 py-0.5 rounded-full border border-rose-800/40">
                  <AlertCircle className="w-3 h-3" /> Unreachable
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Endpoint: <span className="text-slate-300 font-mono">/health</span>
            </p>
            {health?.data && (
              <p className="text-xs text-slate-400 mt-1">
                Env: <span className="text-slate-300 font-mono">{health.data.environment}</span>
              </p>
            )}
          </div>

          {/* PostgreSQL Card */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center gap-2">
                <Database className="w-4 h-4 text-slate-400" />
                Supabase PostgreSQL
              </span>
              {health?.success && health?.data?.database_connected ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded-full border border-emerald-800/40">
                  <CheckCircle2 className="w-3 h-3" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-400 bg-amber-950/50 px-2 py-0.5 rounded-full border border-amber-800/40">
                  <AlertCircle className="w-3 h-3" /> Awaiting Supabase
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Latency: <span className="text-slate-300 font-mono">{health?.data?.database_latency_ms ? `${health.data.database_latency_ms} ms` : 'N/A'}</span>
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Engine: <span className="text-slate-300 font-mono">SQLAlchemy 2.0 (Psycopg 3)</span>
            </p>
          </div>

          {/* API Documentation */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
            <div>
              <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
                Swagger Docs
              </span>
              <p className="text-xs text-slate-400 mt-1">
                Interactive OpenAPI interface for testing backend routes.
              </p>
            </div>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 font-medium mt-3"
            >
              Open Swagger UI <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {lastChecked && (
          <p className="text-[11px] text-slate-500 mt-4 text-right">
            Last polled at: {lastChecked}
          </p>
        )}
      </div>

      {/* 4 Agent Workspaces Overview */}
      <div>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-white">
            Team Agent Architecture (4 Assigned Modules)
          </h2>
          <p className="text-xs text-slate-400">
            Dedicated scaffold directories created for each member to work concurrently without merge conflicts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-lg border ${agent.color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-medium text-slate-200 text-sm">
                        {agent.name}
                      </h3>
                      <span className="text-xs text-slate-400 font-mono">
                        {agent.developer}
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    {agent.status}
                  </span>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <p className="text-[11px] text-slate-400">
                    Directory: <code className="text-slate-300 font-mono bg-slate-950 px-1.5 py-0.5 rounded">{agent.dir}</code>
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
