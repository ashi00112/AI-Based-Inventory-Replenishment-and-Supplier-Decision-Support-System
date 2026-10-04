import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getCurrentUser } from '../services/authApi';
import { getAccessToken, removeAccessToken } from '../services/tokenStorage';

const AuthContext = createContext(null);

/**
 * Authentication Provider component.
 * Manages authenticated user state across the application,
 * validates access tokens on app load, restores sessions across page refreshes,
 * and purges invalid/expired tokens upon 401 responses.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Refreshes or loads the current user profile from GET /api/v1/auth/me.
   * - If no token in sessionStorage: sets user to null.
   * - If /auth/me returns 200: sets user state.
   * - If /auth/me returns 401: purges token from sessionStorage and clears user state.
   * - If temporary network error: leaves token intact and does not falsely mark as invalid.
   */
  const refreshCurrentUser = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      return null;
    }

    const result = await getCurrentUser();

    if (result.success) {
      setUser(result.data);
      return result.data;
    } else if (result.isUnauthorized) {
      // Token is invalid/expired/tampered or user is inactive: purge token
      removeAccessToken();
      setUser(null);
      return null;
    } else {
      // Ordinary network or transient error: do not clear token
      setUser(null);
      return null;
    }
  }, []);

  /**
   * Logs out the current user:
   * 1. Removes the JWT from centralized tokenStorage (sessionStorage).
   * 2. Resets user state to null (marking isAuthenticated as false).
   */
  const logout = useCallback(() => {
    removeAccessToken();
    setUser(null);
  }, []);


  // Initialize session state on application startup / page refresh
  useEffect(() => {
    let isMounted = true;

    async function initializeAuth() {
      const token = getAccessToken();
      if (!token) {
        if (isMounted) {
          setUser(null);
          setIsLoading(false);
        }
        return;
      }

      const result = await getCurrentUser();
      if (!isMounted) return;

      if (result.success) {
        setUser(result.data);
      } else if (result.isUnauthorized) {
        // 401: Invalid or expired token
        removeAccessToken();
        setUser(null);
      } else {
        // Network/connectivity issue: do not remove token
        setUser(null);
      }

      setIsLoading(false);
    }

    initializeAuth();

    return () => {
      isMounted = false;
    };
  }, []);

  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'admin';
  const isStaff = role === 'staff' || role === 'user';

  const value = {
    user,
    role,
    isAdmin,
    isStaff,
    isAuthenticated: !!user,
    isLoading,
    refreshCurrentUser,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Custom hook to consume the AuthContext.
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
