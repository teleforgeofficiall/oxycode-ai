import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { useAuth } from '@/contexts/auth-context';

export interface CloudflareGateResult {
  connected: boolean;
  loading: boolean;
  accountName?: string;
  email?: string;
}

export function useCloudflareGate(): CloudflareGateResult {
  const { token } = useAuth();

  const { data: cfStatus, isLoading } = useQuery({
    queryKey: ['cloudflare-status'],
    queryFn: async () => {
      const res = await apiClient.get('/api/cloudflare/status');
      return res.data;
    },
    enabled: !!token,
  });

  return {
    connected: cfStatus?.account?.connected ?? false,
    loading: isLoading,
    accountName: cfStatus?.account?.accountName,
    email: cfStatus?.account?.email,
  };
}

export function getDeployGateDialog(): {
  title: string;
  message: string;
  actionLabel: string;
  actionUrl: string;
} {
  return {
    title: 'Connect Cloudflare',
    message: 'To deploy your project, connect your Cloudflare account first.',
    actionLabel: 'Connect in Profile',
    actionUrl: '/profile',
  };
}
