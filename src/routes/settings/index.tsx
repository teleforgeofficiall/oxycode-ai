import { useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import {
  ArrowLeft, User, CreditCard, Robot, Cloud, Plug, ArrowSquareOut,
  Spinner, CheckCircle, CaretDown, CaretUp, Lightning, Globe,
  Database, Eye, Shield, HardDrives,
} from '@phosphor-icons/react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { motion, AnimatePresence } from 'framer-motion';

const AVATAR_COLORS = [
  'bg-violet-500', 'bg-blue-500', 'bg-emerald-500', 'bg-amber-500',
  'bg-rose-500', 'bg-cyan-500', 'bg-fuchsia-500', 'bg-teal-500',
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

const CF_BENEFITS = [
  { icon: Eye, label: 'Live Preview', desc: 'See your website in real-time as AI builds it' },
  { icon: Lightning, label: 'One-Click Deploy', desc: 'Deploy to Pages & Workers instantly' },
  { icon: Database, label: 'AI Gateway', desc: 'Smart routing for faster, cheaper AI inference' },
  { icon: Globe, label: 'Custom Domains', desc: 'Use your own domain on deployed projects' },
  { icon: HardDrives, label: 'Global CDN', desc: 'Blazing fast load times worldwide' },
  { icon: Shield, label: 'Zero Config', desc: 'No servers, no VPS — fully serverless' },
];

export default function SettingsPage() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const queryClient = useQueryClient();
  const [cfExpanded, setCfExpanded] = useState(false);

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
      const res = await fetch('/api/limits', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to fetch limits');
      return res.json();
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
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      window.open(
        data.url,
        'cloudflare-oauth',
        `width=${width},height=${height},left=${left},top=${top}`
      );
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
  const isConnected = cf?.connected;

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
        {/* Telegram Profile Card */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-6">
          <div className="flex flex-col items-center gap-4">
            {user?.photo_url ? (
              <img
                src={user.photo_url}
                alt={user.first_name}
                className="size-24 rounded-full object-cover ring-2 ring-kumo-line"
              />
            ) : (
              <div
                className={`size-24 rounded-full flex items-center justify-center text-4xl font-bold text-white ${getAvatarColor(user?.first_name || 'U')}`}
              >
                {(user?.first_name || 'U').charAt(0).toUpperCase()}
              </div>
            )}
            <div className="text-center">
              <h2 className="text-xl font-bold text-kumo-default">
                {user?.first_name || 'User'}
                {user?.last_name ? ` ${user.last_name}` : ''}
              </h2>
              <p className="text-sm text-kumo-subtle mt-1">
                @{user?.username || 'unknown'} • ID: {user?.id}
              </p>
            </div>
          </div>
        </section>

        {/* Cloudflare Account Section — Expandable */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas overflow-hidden">
          {/* Header — always visible, clickable */}
          <button
            onClick={() => setCfExpanded(!cfExpanded)}
            className="w-full flex items-center gap-3 p-4 hover:bg-bg-3/30 transition-colors"
          >
            <div className="size-10 rounded-lg bg-orange-500/10 flex items-center justify-center shrink-0">
              <Cloud className="size-5 text-orange-500" />
            </div>
            <div className="flex-1 text-left">
              <h2 className="font-semibold text-kumo-default">Cloudflare Account</h2>
              <p className="text-xs text-kumo-subtle">
                {isConnected ? 'Connected — tap to see benefits' : 'Connect to deploy your projects'}
              </p>
            </div>
            {isConnected && (
              <CheckCircle className="size-4 text-green-500 shrink-0" />
            )}
            <motion.div
              animate={{ rotate: cfExpanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              <CaretDown className="size-4 text-kumo-subtle" />
            </motion.div>
          </button>

          {/* Expandable content */}
          <AnimatePresence>
            {cfExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <div className="px-4 pb-4 space-y-3">
                  {/* Benefits list (show when NOT connected) */}
                  {!isConnected && (
                    <div className="space-y-2">
                      {CF_BENEFITS.map((b) => (
                        <div key={b.label} className="flex items-start gap-3 p-2 rounded-lg">
                          <div className="size-8 rounded-md bg-orange-500/10 flex items-center justify-center shrink-0 mt-0.5">
                            <b.icon className="size-4 text-orange-500" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-kumo-default">{b.label}</p>
                            <p className="text-xs text-kumo-subtle">{b.desc}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Connected state */}
                  {isConnected && (
                    <div className="space-y-3">
                      <div className="rounded-lg bg-bg-3 dark:bg-kumo-elevated p-3 space-y-1">
                        <p className="text-sm font-medium text-kumo-default">
                          {cf.account?.accountName || 'Cloudflare Account'}
                        </p>
                        <p className="text-xs text-kumo-subtle">{cf.account?.email}</p>
                      </div>

                      {/* Active benefits */}
                      <div className="grid grid-cols-2 gap-2">
                        {CF_BENEFITS.map((b) => (
                          <div
                            key={b.label}
                            className="flex items-center gap-2 p-2 rounded-lg bg-green-500/5 border border-green-500/20"
                          >
                            <CheckCircle className="size-3.5 text-green-500 shrink-0" />
                            <span className="text-xs text-kumo-default">{b.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Action button */}
                  {isConnected ? (
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
                  ) : (
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
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* AI Provider Section */}
        <section className="rounded-xl border border-kumo-line bg-bg-2 dark:bg-kumo-canvas p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="size-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Robot className="size-5 text-purple-500" />
            </div>
            <div>
              <h2 className="font-semibold text-kumo-default">AI Provider</h2>
              <p className="text-xs text-kumo-subtle">Powered by OXYCODE</p>
            </div>
          </div>
          <div className="rounded-lg bg-bg-3 dark:bg-kumo-elevated p-3">
            <p className="text-sm text-kumo-subtle">
              Paid models — free for OXYCODE users
            </p>
            <p className="text-xs text-kumo-subtle mt-1">
              Claude Opus & Fable 5 • GPT 5 Luna & Sol • More top models ⚡️
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
              <p className="text-xs text-kumo-subtle">Resets at 12:00 AM IST daily</p>
            </div>
          </div>

          {limitsLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <div className="space-y-2">
              {limitsData?.limitCheck?.withinLimits === false && (
                <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-3">
                  <p className="text-sm text-red-500 font-medium">
                    Daily rate limit reached
                  </p>
                  <p className="text-xs text-red-500/70 mt-1">
                    Resets at {limitsData?.usage?.prompts?.window === '24h' ? '12:00 AM IST daily' : '12:00 AM IST'}
                  </p>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-kumo-subtle">Used today</span>
                <span className="font-medium text-kumo-default">
                  {limitsData?.usage?.prompts?.used || 0} / {limitsData?.config?.limit?.maxValue || limitsData?.usage?.prompts?.max || 20}
                </span>
              </div>
              <div className="w-full bg-bg-3 dark:bg-kumo-elevated rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    limitsData?.remaining === 0 ? 'bg-red-500' : 'bg-blue-500'
                  }`}
                  style={{
                    width: `${Math.min(100, ((limitsData?.usage?.prompts?.used || 0) / (limitsData?.config?.limit?.maxValue || limitsData?.usage?.prompts?.max || 20)) * 100)}%`,
                  }}
                />
              </div>
              <p className="text-xs text-kumo-subtle">
                {limitsData?.limitCheck?.withinLimits === false ? 0 : (limitsData?.config?.limit?.maxValue || limitsData?.usage?.prompts?.max || 20) - (limitsData?.usage?.prompts?.used || 0)} messages remaining
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
