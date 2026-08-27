import React from 'react';
import { Outlet } from 'react-router';
import { SidebarProvider, useSidebar } from '@cloudflare/kumo';
import { AppSidebar } from './app-sidebar';
import { MobileMenu } from './mobile-menu';
import { GlobalHeader } from './global-header';
import { HeaderProvider } from './header-context';
import { useRecentApps } from '@/hooks/use-apps';

const SIDEBAR_COOKIE_NAME = 'sidebar_state';
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
const SIDEBAR_KEYBOARD_SHORTCUT = 'b';

function useIsMobile() {
	const [isMobile, setIsMobile] = React.useState(() => {
		if (typeof window === 'undefined') return false;
		const tg = (window as any).Telegram?.WebApp;
		if (tg?.platform === 'ios' || tg?.platform === 'android') return true;
		return window.innerWidth < 1024;
	});

	React.useEffect(() => {
		const mq = window.matchMedia('(max-width: 1023px)');
		const handler = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
		mq.addEventListener('change', handler);
		handler(mq);
		return () => mq.removeEventListener('change', handler);
	}, []);

	return isMobile;
}

interface AppLayoutProps {
	children?: React.ReactNode;
}

function SidebarKeyboardShortcut() {
	const { toggleSidebar } = useSidebar();

	React.useEffect(() => {
		const handleKeyDown = (event: KeyboardEvent) => {
			if (
				event.key === SIDEBAR_KEYBOARD_SHORTCUT &&
				(event.metaKey || event.ctrlKey)
			) {
				event.preventDefault();
				toggleSidebar();
			}
		};

		window.addEventListener('keydown', handleKeyDown);
		return () => window.removeEventListener('keydown', handleKeyDown);
	}, [toggleSidebar]);

	return null;
}

function persistSidebarState(open: boolean) {
	document.cookie = `${SIDEBAR_COOKIE_NAME}=${open}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
}

function getSidebarDefaultOpen(): boolean {
	if (typeof window !== 'undefined' && window.innerWidth < 1024) return false;
	const match = document.cookie.match(
		new RegExp(`(?:^|; )${SIDEBAR_COOKIE_NAME}=([^;]*)`),
	);
	if (!match) return true;
	return match[1] === 'true';
}

function DesktopLayout({ children }: AppLayoutProps) {
	const defaultOpen = React.useMemo(() => getSidebarDefaultOpen(), []);

	return (
		<SidebarProvider
			defaultOpen={defaultOpen}
			collapsible="offcanvas"
			resizable={false}
			mobileBreakpoint={1024}
			onOpenChange={persistSidebarState}
			className="vibesdk-sidebar-wrapper"
		>
			<HeaderProvider>
				<SidebarKeyboardShortcut />
				<AppSidebar />
				<main className="bg-kumo-canvas flex flex-col h-screen relative flex-1 min-w-0 overflow-hidden">
					<GlobalHeader />
					<div className="flex-1 min-h-0 overflow-auto bg-kumo-canvas">
						{children || <Outlet />}
					</div>
				</main>
			</HeaderProvider>
		</SidebarProvider>
	);
}

function MobileLayout({ children }: AppLayoutProps) {
	const { apps: recentApps } = useRecentApps();

	return (
		<HeaderProvider>
			<div className="bg-kumo-canvas flex flex-col h-screen relative flex-1 min-w-0 overflow-hidden">
				<header className="flex h-12 shrink-0 items-center border-b border-kumo-line px-4 bg-kumo-canvas">
					<MobileMenu recentApps={recentApps} />
					<div className="flex-1" />
					<div className="flex items-center gap-2">
						<span className="text-lg font-bold uppercase tracking-wide text-kumo-strong">👾</span>
					</div>
				</header>
				<div className="flex-1 min-h-0 overflow-auto bg-kumo-canvas">
					{children || <Outlet />}
				</div>
			</div>
		</HeaderProvider>
	);
}

export function AppLayout({ children }: AppLayoutProps) {
	const isMobile = useIsMobile();

	if (isMobile) {
		return <MobileLayout>{children}</MobileLayout>;
	}

	return <DesktopLayout>{children}</DesktopLayout>;
}
