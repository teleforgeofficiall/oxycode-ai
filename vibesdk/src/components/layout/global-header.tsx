import { useLocation, useNavigate } from 'react-router';
import { SidebarTrigger, useSidebar } from '@cloudflare/kumo';
import { UserCircleIcon } from '@phosphor-icons/react';
import { useHeaderContent } from './header-context';

export function GlobalHeader() {
  const { pathname } = useLocation();
  const { isMobile } = useSidebar();
  const navigate = useNavigate();
  const { content } = useHeaderContent();

  // Don't show header on chat pages (chat has its own header)
  if (pathname.startsWith('/chat/')) return null;

  return (
    <header className="sticky top-0 z-10">
      <div className="relative flex h-12 items-center gap-2 border-b border-kumo-line pl-2 pr-3 md:gap-3 md:px-4">
        {isMobile ? (
          <SidebarTrigger
            aria-label="Toggle sidebar"
            className="shrink-0"
          />
        ) : null}

        <div className="min-w-0 flex-1 flex items-center gap-2">
          {content?.leading}
        </div>

        <div className="flex items-center justify-end gap-1.5 shrink-0">
          {content?.trailing}
          <button
            onClick={() => navigate('/profile')}
            className="size-8 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors"
          >
            <UserCircleIcon className="size-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
