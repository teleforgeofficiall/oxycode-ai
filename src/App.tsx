import { useState } from 'react';
import { Outlet } from 'react-router';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { AuthProvider } from './contexts/auth-context';
import { ThemeProvider } from './contexts/theme-context';
import { Toaster } from 'sonner';
import { AppLayout } from './components/layout/app-layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { createQueryClient, queryPersistOptions } from './lib/query-client';

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
						<AppLayout>
							<Outlet />
						</AppLayout>
						<Toaster
							richColors
							position="top-right"
						/>
					</AuthProvider>
				</ThemeProvider>
			</PersistQueryClientProvider>
		</ErrorBoundary>
	);
}
