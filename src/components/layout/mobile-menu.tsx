import { useState, useEffect, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { PlusIcon, UserCircle, ListIcon, XIcon } from '@phosphor-icons/react';
import { useAuth } from '@/contexts/auth-context';
import { ThemeToggle } from '@/components/theme-toggle';

interface MobileMenuProps {
  recentApps: Array<{ id: string; name: string; updatedAt: Date | string | null }>;
}

export function MobileMenu({ recentApps }: MobileMenuProps) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    close();
  }, [pathname, close]);

  const formatTimestamp = (updatedAt: Date | string | null) => {
    if (!updatedAt) return '';
    const date = updatedAt instanceof Date ? updatedAt : new Date(updatedAt);
    const diff = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diff < 60) return 'now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="size-9 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors"
        aria-label="Open menu"
      >
        <ListIcon className="size-5" />
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-50"
            onClick={close}
          />
          <div className="fixed inset-y-0 left-0 z-50 w-72 bg-kumo-canvas border-r border-kumo-line flex flex-col shadow-xl">
            <div className="flex items-center justify-between px-4 h-12 border-b border-kumo-line">
              <Link to="/" className="flex items-center gap-2.5 text-kumo-strong" onClick={close}>
                <span className="text-xl">👾</span>
                <span className="text-base font-black uppercase tracking-wide">OXYCODE</span>
              </Link>
              <button
                onClick={close}
                className="size-8 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50"
                aria-label="Close menu"
              >
                <XIcon className="size-4" />
              </button>
            </div>

            <div className="px-3 py-3">
              {pathname !== '/' && (
                <button
                  onClick={() => { navigate('/'); close(); }}
                  className="w-full h-9 rounded-lg bg-brand-emphasis text-white flex items-center justify-center gap-2 text-sm hover:bg-brand-emphasis/90"
                >
                  <PlusIcon className="size-4" weight="bold" />
                  New Build
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto px-2">
              {recentApps.length > 0 && (
                <div className="mb-4">
                  <div className="px-2 py-1.5 text-xs uppercase text-kumo-subtle">Projects</div>
                  <div className="flex flex-col gap-0.5">
                    {recentApps.map((app) => (
                      <button
                        key={app.id}
                        onClick={() => { navigate(`/chat/${app.id}`); close(); }}
                        className={`flex flex-col gap-0.5 px-3 py-2 rounded-lg text-left transition-colors ${
                          pathname === `/chat/${app.id}` ? 'bg-bg-4/50 text-kumo-default' : 'text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/30'
                        }`}
                      >
                        <span className="text-sm truncate">{app.name}</span>
                        {app.updatedAt && (
                          <span className="text-xs text-kumo-subtle">{formatTimestamp(app.updatedAt)}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="px-3 py-3 border-t border-kumo-line">
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <button
                    onClick={() => { navigate('/profile'); close(); }}
                    className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors"
                  >
                    <UserCircle className="size-4" />
                    <span>{user?.first_name || 'Profile'}</span>
                  </button>
                </div>
                <ThemeToggle align="end" className="size-9 shrink-0 rounded-lg" />
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
