/**
 * OXYCODE AI — Telegram Auth Context
 * Authenticates via Telegram Mini App initData. No login page needed.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from 'react';
import { useNavigate } from 'react-router';

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
}

interface AuthContextType {
  user: TelegramUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  isMaintenance: boolean;
  isAdmin: boolean;
  login: () => void;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

function getTelegramInitData(): string | null {
  const tg = window.Telegram?.WebApp;
  if (!tg) return null;
  return tg.initData || null;
}

function getTelegramUser(): TelegramUser | null {
  const tg = window.Telegram?.WebApp;
  if (!tg?.initDataUnsafe?.user) return null;
  return tg.initDataUnsafe.user;
}

async function authenticateWithBackend(
  initData: string,
): Promise<{ token: string; user: TelegramUser; maintenance: boolean; isAdmin: boolean }> {
  const response = await fetch(`${API_BASE}/api/auth/telegram`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ initData: initData }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Auth failed' }));
    throw new Error(error.detail || 'Authentication failed');
  }

  return response.json();
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(() => {
    try {
      return localStorage.getItem('oxycode_token');
    } catch {
      return null;
    }
  });
  const [user, setUser] = useState<TelegramUser | null>(() => {
    try {
      const stored = localStorage.getItem('oxycode_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isMaintenance, setIsMaintenance] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    async function initAuth() {
      const initData = getTelegramInitData();
      const tgUser = getTelegramUser();

      if (!initData || !tgUser) {
        // Not in Telegram Mini App — use stored credentials if available
        setIsLoading(false);
        return;
      }

      // Already authenticated with same user — still call backend for maintenance/isAdmin
      if (token && user?.id === tgUser.id) {
        try {
          const result = await authenticateWithBackend(initData);
          setIsMaintenance(result.maintenance);
          setIsAdmin(result.isAdmin);
        } catch {
          // Ignore errors — use cached auth state
        }
        setIsLoading(false);
        return;
      }

      try {
        const result = await authenticateWithBackend(initData);
        setToken(result.token);
        setUser(result.user);
        setIsMaintenance(result.maintenance);
        setIsAdmin(result.isAdmin);
        localStorage.setItem('oxycode_token', result.token);
        localStorage.setItem('oxycode_user', JSON.stringify(result.user));
      } catch (err) {
        console.error('Telegram auth failed:', err);
        // Handle maintenance 503 responses
        if (err instanceof Error && err.message.includes('maintenance')) {
          setIsMaintenance(true);
          setIsLoading(false);
          return;
        }
        setError(err instanceof Error ? err.message : 'Authentication failed');
        // Clear stale credentials
        localStorage.removeItem('oxycode_token');
        localStorage.removeItem('oxycode_user');
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    void initAuth();
  }, []);

  const login = useCallback(() => {
    // In Telegram Mini App, auth happens automatically on load
    // This is a no-op — the Mini App context handles it
    void navigate('/');
  }, [navigate]);

  const logout = useCallback(async () => {
    localStorage.removeItem('oxycode_token');
    localStorage.removeItem('oxycode_user');
    setToken(null);
    setUser(null);
    navigate('/');
  }, [navigate]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      isAuthenticated: !!token && !!user,
      isLoading,
      error,
      isMaintenance,
      isAdmin,
      login,
      logout,
      clearError,
    }),
    [user, token, isLoading, error, isMaintenance, isAdmin, login, logout, clearError],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function useRequireAuth(redirectTo = '/') {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate(redirectTo);
    }
  }, [isAuthenticated, isLoading, navigate, redirectTo]);

  return { isAuthenticated, isLoading };
}
