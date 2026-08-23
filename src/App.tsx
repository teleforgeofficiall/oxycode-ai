import { useState } from 'react';
import { Outlet } from 'react-router';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { AuthProvider, useAuth } from './contexts/auth-context';
import { LimitsProvider } from './contexts/limits-context';
import { ThemeProvider } from './contexts/theme-context';
import { Toaster } from 'sonner';
import { AppLayout } from './components/layout/app-layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { MaintenancePage } from './components/maintenance-page';
import { createQueryClient, queryPersistOptions } from './lib/query-client';
import { Spinner } from '@phosphor-icons/react';

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
			<PersistQueryClientProvider
				client={queryClient}
				persistOptions={queryPersistOptions}
			>
				<ThemeProvider>
					<AuthProvider>
						<LimitsProvider>
							<AppInner />
						</LimitsProvider>
					</AuthProvider>
				</ThemeProvider>
			</PersistQueryClientProvider>
		</ErrorBoundary>
	);
}
