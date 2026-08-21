import React from 'react';
import { PlusIcon, UserCircleIcon, HouseIcon } from '@phosphor-icons/react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Sidebar, cn, useSidebar } from '@cloudflare/kumo';
import { useAuth } from '@/contexts/auth-context';
import { useRecentApps } from '@/hooks/use-apps';
import { ThemeToggle } from '@/components/theme-toggle';

interface App {
	id: string;
	title: string;
	updatedAt: Date | string | null;
}

function AppMenuItem({
	app,
	onClick,
	active,
	isCollapsed,
}: {
	app: App;
	onClick: () => void;
	active: boolean;
	isCollapsed: boolean;
}) {
	const formatTimestamp = () => {
		const updatedAt =
			app.updatedAt instanceof Date
				? app.updatedAt
				: app.updatedAt
					? new Date(app.updatedAt)
					: null;
		if (!updatedAt) return '';
		const diff = Math.floor((Date.now() - updatedAt.getTime()) / 1000);
		if (diff < 60) return 'now';
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return `${Math.floor(diff / 86400)}d ago`;
	};

	return (
		<Sidebar.MenuItem>
			<Sidebar.MenuButton
				active={active}
				tooltip={app.title}
				className="min-h-10 items-start py-2 text-sm"
				onClick={(e) => {
					e.preventDefault();
					onClick();
				}}
			>
				<span className="flex min-w-0 flex-1 flex-col gap-1">
					<span className="truncate text-kumo-default">{app.title}</span>
					<span className="text-xs text-kumo-subtle">{formatTimestamp()}</span>
				</span>
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
	);
}

export function AppSidebar() {
	const { user } = useAuth();
	const navigate = useNavigate();
	const { pathname } = useLocation();
	const { state } = useSidebar();
	const isCollapsed = state === 'collapsed';
	const { apps: recentApps } = useRecentApps();

	return (
		<Sidebar className="[--sidebar-bg:var(--color-kumo-canvas)]">
			<Sidebar.Header
				className={cn(
					'h-12',
					isCollapsed ? 'justify-center px-0' : 'px-3',
				)}
			>
				{isCollapsed ? (
					<div className="flex size-9 items-center justify-center text-xl font-bold">
						👾
					</div>
				) : (
					<div className="flex w-full min-w-0 items-center gap-2.5">
						<Link
							to="/"
							className="flex min-w-0 flex-1 items-center gap-2.5 text-kumo-strong"
						>
							<span className="text-xl">👾</span>
							<span className="min-w-0 flex-1 truncate text-base font-black uppercase tracking-wide">
								OXYCODE
							</span>
						</Link>
						<Sidebar.Trigger
							aria-label="Collapse sidebar"
							className="ml-auto shrink-0"
						/>
					</div>
				)}
			</Sidebar.Header>

			<div className="shrink-0 px-[11px] py-3 group-not-data-[state=collapsed]/sidebar:px-3.5">
				{isCollapsed ? (
					<div className="flex flex-col items-center gap-1">
						{pathname !== '/' && (
							<button
								onClick={() => navigate('/')}
								className="size-8 rounded-lg bg-brand-emphasis text-white flex items-center justify-center hover:bg-brand-emphasis/90"
								aria-label="New build"
							>
								<PlusIcon className="size-4" weight="bold" />
							</button>
						)}
					</div>
				) : (
					<div className="flex flex-col gap-1.5">
						{pathname !== '/' && (
							<button
								onClick={() => navigate('/')}
								className="w-full h-8 rounded-lg bg-brand-emphasis text-white flex items-center justify-center gap-2 text-sm hover:bg-brand-emphasis/90"
							>
								<PlusIcon className="size-4" weight="bold" />
								New Build
							</button>
						)}
					</div>
				)}
			</div>

			<Sidebar.Content>
				{!isCollapsed && recentApps.length > 0 && (
					<Sidebar.Group>
						<Sidebar.GroupLabel>
							<span className="text-xs uppercase">Projects</span>
						</Sidebar.GroupLabel>
						<Sidebar.Menu>
							{recentApps.map((app) => (
								<AppMenuItem
									key={app.id}
									app={app}
									onClick={() => navigate(`/chat/${app.id}`)}
									active={pathname === `/chat/${app.id}`}
									isCollapsed={isCollapsed}
								/>
							))}
						</Sidebar.Menu>
					</Sidebar.Group>
				)}
			</Sidebar.Content>

			<Sidebar.Footer className="h-auto p-3">
				{/* User Profile Card */}
				{!isCollapsed && user && (
					<button
						onClick={() => navigate('/profile')}
						className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 mb-1.5 text-left hover:bg-bg-4/50 transition-colors"
					>
						<div className="size-9 rounded-full bg-brand-emphasis/20 flex items-center justify-center text-sm font-bold text-brand-emphasis shrink-0">
							{user.firstName?.charAt(0) || '👤'}
						</div>
						<div className="min-w-0 flex-1">
							<p className="text-sm font-medium text-kumo-default truncate">
								{user.firstName || 'User'}
							</p>
							<p className="text-xs text-kumo-subtle truncate">
								@{user.username || 'username'}
							</p>
						</div>
					</button>
				)}

				{/* Collapsed profile avatar */}
				{isCollapsed && user && (
					<button
						onClick={() => navigate('/profile')}
						className="flex items-center justify-center mb-1.5"
					>
						<div className="size-8 rounded-full bg-brand-emphasis/20 flex items-center justify-center text-sm font-bold text-brand-emphasis">
							{user.firstName?.charAt(0) || '👤'}
						</div>
					</button>
				)}

				<div className="flex w-full min-w-0 items-center gap-2">
					<div className="min-w-0 flex-1">
						<button
							onClick={() => navigate('/profile')}
							className={cn(
								'flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors',
							)}
						>
							<UserCircleIcon className="size-4" />
							{!isCollapsed && <span>Profile</span>}
						</button>
					</div>
					<ThemeToggle
						align="end"
						className="size-9 shrink-0 rounded-lg"
					/>
				</div>
			</Sidebar.Footer>
		</Sidebar>
	);
}
