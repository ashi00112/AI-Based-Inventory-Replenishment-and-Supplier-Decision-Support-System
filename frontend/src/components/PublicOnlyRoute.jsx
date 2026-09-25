import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';

/**
 * Route guard for guest/public-only authentication pages (/login, /register).
 *
 * Behavior:
 * - If isLoading is true: renders a subtle loading indicator without premature redirect.
 * - If isAuthenticated is true: redirects already-authenticated users to the main dashboard (/).
 * - Else: renders public authentication page children.
 */
export default function PublicOnlyRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
        <span className="text-xs font-mono tracking-wider text-slate-500">
          Checking session...
        </span>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}
