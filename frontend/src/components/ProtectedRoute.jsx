import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';

/**
 * Reusable route guard for authenticated application pages.
 *
 * Behavior:
 * - If isLoading is true: renders a non-redirecting loading indicator while session state resolves.
 * - If isAuthenticated is false: redirects unauthenticated users to /login via React Router.
 * - Else: renders protected children components.
 */
export default function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
        <span className="text-xs font-mono tracking-wider text-slate-500">
          Verifying session...
        </span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
