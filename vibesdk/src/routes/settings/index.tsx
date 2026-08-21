import React from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { ArrowLeft, CreditCard, Cloud, Plugs, ArrowSquareOut, Spinner, CheckCircle } from '@phosphor-icons/react';
import { UserAvatar } from '@/components/user-avatar';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

function useCountdown(resetAt: string | null) {
  const [timeLeft, setTimeLeft] = React.useState('');

  React.useEffect(() => {
    if (!resetAt) {
      setTimeLeft('');
      return;
    }

    const update = () => {
      const now = Date.now();
      const reset = new Date(resetAt).getTime();
      const diff = reset - now;

      if (diff <= 0) {
        setTimeLeft('Resetting...');
        return;
      }

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      setTimeLeft(`${hours}h ${minutes}m`);
    };

    update();
    const interval = setInterval(update, 60000);
    return () => clearInterval(interval);
  }, [resetAt]);

  return timeLeft;
}

function DailyUsageSection({ limitsData, limitsLoading }: { limitsData: any; limitsLoading: boolean }) {
  const resetAt = limitsData?.resetAt || null;
  const timeLeft = useCountdown(resetAt);
  const used = limitsData?.used || 0;
  const limit = limitsData?.limit || 20;
  const remaining = limitsData?.remaining || 0;
  const percentage = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;

  return (
    <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="size-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
          <CreditCard className="size-5 text-blue-500" />
        </div>
        <div>
          <h2 className="font-semibold text-kumo-default">Usage</h2>
          <p className="text-xs text-kumo-subtle">Rolling 24-hour window</p>
        </div>
      </div>

      {limitsLoading ? (
        <Skeleton className="h-10 w-full" />
      ) : (
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-kumo-subtle">Prompts used</span>
            <span className="font-medium text-kumo-default">
              {used} / {limit}
            </span>
          </div>

          <div className="w-full bg-bg-3 dark:bg-kumo-elevated rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all ${
                percentage >= 100
                  ? 'bg-red-500'
                  : percentage >= 80
                    ? 'bg-yellow-500'
                    : 'bg-blue-500'
              }`}
              style={{ width: `${percentage}%` }}
            />
          </div>

          {percentage >= 100 ? (
            <p className="text-xs text-red-500 font-medium">
              Limit reached · Resets in {timeLeft}
            </p>
          ) : (
            <p className="text-xs text-kumo-subtle">
              {remaining} prompts remaining
              {timeLeft && (
                <span className="ml-1">· Resets in {timeLeft}</span>
              )}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const queryClient = useQueryClient();

  // Fetch Cloudflare status
  const { data: cfStatus, isLoading: cfLoading, error: cfError } = useQuery({
    queryKey: ['cloudflare-status'],
    queryFn: async () => {
      const res = await apiClient.get('/api/cloudflare/status');
      return res.data;
    },
    enabled: !!token,
    throwOnError: false,
    retry: false,
  });

  // Fetch user limits
  const { data: limitsData, isLoading: limitsLoading, error: limitsError } = useQuery({
    queryKey: ['limits'],
    queryFn: async () => {
      const res = await apiClient.get('/api/limits');
      return res.data;
    },
    enabled: !!token,
    throwOnError: false,
    retry: false,
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
            onClick={() => navigate('/')}
            className="size-9 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-4/50 transition-colors"
          >
            <ArrowLeft className="size-5" />
          </button>
          <h1 className="text-lg font-semibold text-kumo-default">Profile</h1>
        </div>
      </div>

      <div className="p-4 space-y-4 max-w-lg mx-auto">
        {/* User Profile */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
          <div className="flex items-center gap-4">
            <UserAvatar
              photoUrl={user?.photo_url}
              name={user?.first_name || 'User'}
              size="lg"
            />
            <div>
              <h2 className="text-lg font-semibold text-kumo-default">
                {user?.first_name} {user?.last_name || ''}
              </h2>
              <p className="text-sm text-kumo-subtle">
                @{user?.username || 'unknown'} • ID: {user?.id}
              </p>
            </div>
          </div>
        </section>

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

          {cfError ? (
            <p className="text-sm text-kumo-subtle">
              Unable to load Cloudflare status. Please try again later.
            </p>
          ) : cfLoading ? (
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
                  <Plugs className="size-4 mr-2" />
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

        {/* Daily Usage Section */}
        {limitsError ? (
          <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
            <p className="text-sm text-kumo-subtle">
              Unable to load usage data. Please try again later.
            </p>
          </section>
        ) : (
          <DailyUsageSection limitsData={limitsData} limitsLoading={limitsLoading} />
        )}

      </div>
    </div>
  );
}
