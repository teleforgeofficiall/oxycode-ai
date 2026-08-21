/**
 * Auth Modal Provider
 * Simple auth modal for the Mini App MVP.
 * In Telegram Mini App, auth is automatic via initData.
 */

import { createContext, useContext, useCallback, ReactNode } from 'react';

interface AuthModalContextType {
  showAuthModal: (context?: string, onSuccess?: () => void, intendedUrl?: string) => void;
}

const AuthModalContext = createContext<AuthModalContextType>({
  showAuthModal: () => {},
});

export function AuthModalProvider({ children }: { children: ReactNode }) {
  const showAuthModal = useCallback((context?: string, onSuccess?: () => void, intendedUrl?: string) => {
    // In Telegram Mini App, auth is handled by the bot.
    // This is a fallback for web-only usage.
    console.log('Auth modal requested:', { context, intendedUrl });
    alert('Please open this app from Telegram to authenticate.');
  }, []);

  return (
    <AuthModalContext.Provider value={{ showAuthModal }}>
      {children}
    </AuthModalContext.Provider>
  );
}

export function useAuthModal() {
  return useContext(AuthModalContext);
}
