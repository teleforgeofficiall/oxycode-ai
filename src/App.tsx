import { useState } from 'react';
import { Outlet } from 'react-router';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { AuthProvider, useAuth } from './contexts/auth-context';
import { ThemeProvider } from './contexts/theme-context';
import { Toaster } from 'sonner';
import { AppLayout } from './components/layout/app-layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { MaintenanceOverlay } from './components/maintenance-overlay';
import { createQueryClient, queryPersistOptions } from './lib/query-client';

function AppInner() {
	const { isMaintenance } = useAuth();

	return (
		<>
			{isMaintenance && <MaintenanceOverlay />}
			{!isMaintenance && (
				<AppLayout>
					<Outlet />
				</AppLayout>
			)}
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
						<AppInner />
					</AuthProvider>
				</ThemeProvider>
			</PersistQueryClientProvider>
		</ErrorBoundary>
	);
}
