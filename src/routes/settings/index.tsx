import { useAuth } from '@/contexts/auth-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { ArrowLeft, User, CreditCard, Bot, Cloud, Plug, ArrowSquareOut, Spinner, CheckCircle } from '@phosphor-icons/react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export default function SettingsPage() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const queryClient = useQueryClient();

  // Fetch Cloudflare status
  const { data: cfStatus, isLoading: cfLoading } = useQuery({
    queryKey: ['cloudflare-status'],
    queryFn: async () => {
      const res = await apiClient.get('/api/cloudflare/status');
      return res.data;
    },
    enabled: !!token,
  });

  // Fetch user limits
  const { data: limitsData, isLoading: limitsLoading } = useQuery({
    queryKey: ['limits'],
    queryFn: async () => {
      const res = await apiClient.get('/api/limits');
      return res.data;
    },
    enabled: !!token,
  });

  // Connect Cloudflare mutation
  const connectMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.get('/api/cloudflare/auth-url');
      return res.data;
    },
    onSuccess: (data) => {
      // Open OAuth popup
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      window.open(
        data.url,
        'cloudflare-oauth',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      // Listen for popup close (callback page will postMessage)
      const listener = (event: MessageEvent) => {
        if (event.data === 'cloudflare-connected') {
          queryClient.invalidateQueries({ queryKey: ['cloudflare-status'] });
          window.removeEventListener('message', listener);
        }
      };
      window.addEventListener('message', listener);
    },
  });

  // Disconnect Cloudflare mutation
  const disconnectMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete('/api/cloudflare/disconnect');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cloudflare-status'] });
    },
  });

  const cf = cfStatus?.account;

  return (
    <div className="min-h-screen bg-bg-1 dark:bg-kumo-base">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-bg-2/80 dark:bg-kumo-canvas/80 backdrop-blur-md border-b border-kumo-line">
        <div className="flex items-center gap-3 px-4 py-3">
          <button
            onClick={() => navigate(-1)}
            className="size-9 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors"
          >
            <ArrowLeft className="size-5" />
          </button>
          <h1 className="text-lg font-semibold text-kumo-default">Settings</h1>
        </div>
      </div>

      <div className="p-4 space-y-4 max-w-lg mx-auto">
        {/* Cloudflare Account Section */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="size-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <Cloud className="size-5 text-orange-500" />
            </div>
            <div>
              <h2 className="font-semibold text-kumo-default">Cloudflare Account</h2>
              <p className="text-xs text-kumo-subtle">
                Connect to deploy your projects
              </p>
            </div>
          </div>

          {cfLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : cf?.connected ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm text-kumo-subtle">
                <CheckCircle className="size-4 text-green-500" />
                <span>Connected</span>
              </div>
              <div className="rounded-lg bg-bg-3 dark:bg-kumo-elevated p-3 space-y-1">
                <p className="text-sm font-medium text-kumo-default">
                  {cf.account?.accountName || 'Cloudflare Account'}
                </p>
                <p className="text-xs text-kumo-subtle">
                  {cf.account?.email}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full text-red-500 border-red-500/30 hover:bg-red-500/10"
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
              >
                {disconnectMutation.isPending ? (
                  <Spinner className="size-4 mr-2 animate-spin" />
                ) : (
                  <Plug className="size-4 mr-2" />
                )}
                Disconnect
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-kumo-subtle">
                Connect your Cloudflare account to deploy websites to Pages and bots to Workers.
              </p>
              <Button
                className="w-full bg-orange-500 hover:bg-orange-600 text-white"
                onClick={() => connectMutation.mutate()}
                disabled={connectMutation.isPending}
              >
                {connectMutation.isPending ? (
                  <Spinner className="size-4 mr-2 animate-spin" />
                ) : (
                  <ArrowSquareOut className="size-4 mr-2" />
                )}
                Connect Cloudflare
              </Button>
            </div>
          )}
        </section>

        {/* AI Provider Section */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="size-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Bot className="size-5 text-purple-500" />
            </div>
            <div>
              <h2 className="font-semibold text-kumo-default">AI Provider</h2>
              <p className="text-xs text-kumo-subtle">Powered by OpenCode Zen</p>
            </div>
          </div>
          <div className="rounded-lg bg-bg-3 dark:bg-kumo-elevated p-3">
            <p className="text-sm text-kumo-subtle">
              Free models (no API key required)
            </p>
            <p className="text-xs text-kumo-subtle mt-1">
              mimo-v2.5-free → deepseek-v4-flash-free → hy3-free
            </p>
          </div>
        </section>

        {/* Daily Usage Section */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="size-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <CreditCard className="size-5 text-blue-500" />
            </div>
            <div>
              <h2 className="font-semibold text-kumo-default">Daily Usage</h2>
              <p className="text-xs text-kumo-subtle">Messages reset at midnight UTC</p>
            </div>
          </div>

          {limitsLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-kumo-subtle">Used today</span>
                <span className="font-medium text-kumo-default">
                  {limitsData?.usedToday || 0} / {limitsData?.dailyLimit || 20}
                </span>
              </div>
              <div className="w-full bg-bg-3 dark:bg-kumo-elevated rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, ((limitsData?.usedToday || 0) / (limitsData?.dailyLimit || 20)) * 100)}%`,
                  }}
                />
              </div>
              <p className="text-xs text-kumo-subtle">
                {limitsData?.remaining || 0} messages remaining
              </p>
            </div>
          )}
        </section>

        {/* Telegram Account Section */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg bg-blue-400/10 flex items-center justify-center">
              <User className="size-5 text-blue-400" />
            </div>
            <div>
              <h2 className="font-semibold text-kumo-default">
                {user?.first_name || 'User'}
              </h2>
              <p className="text-xs text-kumo-subtle">
                @{user?.username || 'unknown'} • ID: {user?.id}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
