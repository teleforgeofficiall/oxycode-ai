/**
 * BrowserGate — Blocks non-Telegram access.
 * Shows "Open in Telegram" page when app is opened in a browser.
 * Only allows access when running inside Telegram Mini App.
 */

import { ReactNode } from 'react';

const TELEGRAM_BOT_URL = 'https://t.me/OXYCODE_AI_BOT?startapp';

function isInTelegram(): boolean {
  try {
    const tg = (window as any).Telegram?.WebApp;
    return !!(tg && tg.initData);
  } catch {
    return false;
  }
}

function hasCachedSession(): boolean {
  try {
    return !!(localStorage.getItem('oxycode_token') && localStorage.getItem('oxycode_user'));
  } catch {
    return false;
  }
}

function TelegramGate() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] p-4">
      <div className="max-w-sm w-full space-y-8 text-center">
        <div className="space-y-3">
          <div className="text-6xl">👾</div>
          <h1 className="text-2xl font-black text-white tracking-wide">OXYCODE AI</h1>
          <p className="text-neutral-400 text-sm leading-relaxed">
            This app works inside Telegram.
          </p>
        </div>

        <a
          href={TELEGRAM_BOT_URL}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#2AABEE] text-white font-semibold text-sm hover:bg-[#229ED9] transition-colors w-full justify-center"
        >
          <svg className="size-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
          </svg>
          Open in Telegram
        </a>

        <p className="text-neutral-600 text-xs">
          Tap the button above to open OXYCODE AI in Telegram
        </p>
      </div>
    </div>
  );
}

export function BrowserGate({ children }: { children: ReactNode }) {
  // Allow access if in Telegram OR if user has a cached session
  if (isInTelegram() || hasCachedSession()) {
    return <>{children}</>;
  }

  return <TelegramGate />;
}
