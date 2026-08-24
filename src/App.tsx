import { useState, useEffect } from 'react';
import { Outlet } from 'react-router';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { AuthProvider, useAuth } from './contexts/auth-context';
import { LimitsProvider } from './contexts/limits-context';
import { ThemeProvider } from './contexts/theme-context';
import { BrowserGate } from './components/browser-gate';
import { Toaster } from 'sonner';
import { ToastProvider } from '@cloudflare/kumo';
import { FeatureProvider } from './features';
import { AppLayout } from './components/layout/app-layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { MaintenancePage } from './components/maintenance-page';
import { createQueryClient, queryPersistOptions } from './lib/query-client';
import { Spinner } from '@phosphor-icons/react';

function GlobalErrorCatcher() {
	useEffect(() => {
		const handleError = (event: ErrorEvent) => {
			console.error('[OXYCODE UNCAUGHT]', event.error);
			try {
				localStorage.setItem('oxycode_last_error', JSON.stringify({
					message: event.error?.message || event.message,
					stack: event.error?.stack || '',
					time: new Date().toISOString(),
					url: window.location.href,
					type: 'uncaught',
				}));
			} catch {}
		};
		const handleRejection = (event: PromiseRejectionEvent) => {
			console.error('[OXYCODE UNHANDLED REJECTION]', event.reason);
			try {
				localStorage.setItem('oxycode_last_error', JSON.stringify({
					message: String(event.reason),
					time: new Date().toISOString(),
					url: window.location.href,
					type: 'unhandled_rejection',
				}));
			} catch {}
		};
		window.addEventListener('error', handleError);
		window.addEventListener('unhandledrejection', handleRejection);
		return () => {
			window.removeEventListener('error', handleError);
			window.removeEventListener('unhandledrejection', handleRejection);
		};
	}, []);
	return null;
}

function AppInner() {
	const { isMaintenance, isAdmin, isLoading } = useAuth();
	const showMaintenance = isMaintenance && !isAdmin;

	if (isLoading) {
		return (
			<div className="size-full flex items-center justify-center bg-bg-1">
				<Spinner className="size-8 animate-spin text-brand-emphasis" weight="bold" />
			</div>
		);
	}

	return (
		<>
			<AppLayout>
				{showMaintenance ? <MaintenancePage /> : <Outlet />}
			</AppLayout>
			<Toaster
				richColors
				position="top-right"
			/>
		</>
	);
}

export default function App() {
	const [queryClient] = useState(createQueryClient);

	return (
		<ErrorBoundary>
			<GlobalErrorCatcher />
			<PersistQueryClientProvider
				client={queryClient}
				persistOptions={queryPersistOptions}
			>
				<ThemeProvider>
					<AuthProvider>
						<LimitsProvider>
							<ToastProvider>
								<FeatureProvider>
									<BrowserGate>
										<AppInner />
									</BrowserGate>
								</FeatureProvider>
							</ToastProvider>
						</LimitsProvider>
					</AuthProvider>
				</ThemeProvider>
			</PersistQueryClientProvider>
		</ErrorBoundary>
	);
}
