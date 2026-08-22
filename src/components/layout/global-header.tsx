import { useLocation, Link } from 'react-router';
import { SidebarTrigger, useSidebar } from '@cloudflare/kumo';
import { UserCircle } from '@phosphor-icons/react';

export function GlobalHeader() {
  const { pathname } = useLocation();
  const { state } = useSidebar();
  const isCollapsed = state === 'collapsed';
  // Don't show header on chat pages (chat has its own header)
  if (pathname.startsWith('/chat/')) return null;

  return (
    <header className="flex h-12 shrink-0 items-center border-b border-kumo-line px-4 bg-kumo-canvas">
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        <Link
          to="/profile"
          className="size-8 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors"
        >
          <UserCircle className="size-4" />
        </Link>
      </div>
    </header>
  );
}
