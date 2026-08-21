/**
 * Authentication Guard Hook
 * Provides easy authentication checks for protected actions
 */

import { useCallback } from 'react';
import { useAuth } from '../contexts/auth-context';

export interface AuthGuardOptions {
  requireFullAuth?: boolean;
  actionContext?: string;
  onSuccess?: () => void;
  intendedUrl?: string;
}

export interface AuthGuardReturn {
  isAuthenticated: boolean;
  user: { id: number; username?: string; first_name?: string } | null;
  requireAuth: (options?: AuthGuardOptions) => boolean;
}

export function useAuthGuard(): AuthGuardReturn {
  const { isAuthenticated, user } = useAuth();

  const requireAuth = useCallback((options: AuthGuardOptions = {}) => {
    if (isAuthenticated) {
      if (options.onSuccess) {
        options.onSuccess();
      }
      return true;
    }
    return false;
  }, [isAuthenticated]);

  return {
    isAuthenticated,
    user,
    requireAuth,
  };
}