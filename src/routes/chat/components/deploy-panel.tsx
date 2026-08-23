import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Rocket, Globe, Spinner, CheckCircle, XCircle, ArrowSquareOut,
  Cloud, Code, Copy, Link,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/auth-context';
import { useQuery } from '@tanstack/react-query';
import { getChats, type Chat } from '@/lib/chat-api';

interface DeployPanelProps {
  isOpen: boolean;
  onClose: () => void;
  currentChatId?: number;
  onDeployChat?: (chatId: number) => void;
  isDeploying?: boolean;
  deployedUrl?: string;
}

export function DeployPanel({
  isOpen,
  onClose,
  currentChatId,
  onDeployChat,
  isDeploying,
  deployedUrl,
}: DeployPanelProps) {
  const { token } = useAuth();
  const [copied, setCopied] = useState(false);

  // Fetch all user chats
  const { data: chats, isLoading } = useQuery({
    queryKey: ['chats'],
    queryFn: getChats,
    enabled: !!token && isOpen,
  });

  const handleCopyUrl = () => {
    if (deployedUrl) {
      navigator.clipboard.writeText(deployedUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="overflow-hidden border-t border-kumo-line bg-bg-2 dark:bg-kumo-canvas"
        >
          <div className="p-4 space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cloud className="size-4 text-orange-500" />
                <span className="text-sm font-semibold text-kumo-default">
                  Cloudflare Deploy
                </span>
              </div>
              <button
                onClick={onClose}
                className="text-kumo-subtle hover:text-kumo-default text-xs"
              >
                Close
              </button>
            </div>

            {/* Deployed URL */}
            {deployedUrl && (
              <div className="rounded-lg bg-green-500/10 border border-green-500/30 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle className="size-3.5 text-green-500" />
                  <span className="text-xs font-medium text-green-500">
                    Deployed
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={deployedUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-green-400 hover:underline truncate flex-1"
                  >
                    {deployedUrl}
                  </a>
                  <button
                    onClick={handleCopyUrl}
                    className="text-kumo-subtle hover:text-kumo-default"
                  >
                    {copied ? (
                      <CheckCircle className="size-3.5 text-green-500" />
                    ) : (
                      <Copy className="size-3.5" />
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Current chat deploy */}
            {currentChatId && !deployedUrl && (
              <div className="rounded-lg bg-bg-3 dark:bg-kumo-elevated p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Rocket className="size-4 text-orange-500" />
                  <span className="text-sm font-medium text-kumo-default">
                    Deploy current project
                  </span>
                </div>
                <p className="text-xs text-kumo-subtle mb-3">
                  Deploy this chat project to Cloudflare Pages
                </p>
                <Button
                  className="w-full bg-orange-500 hover:bg-orange-600 text-white"
                  size="sm"
                  disabled={isDeploying}
                  onClick={() => onDeployChat?.(currentChatId)}
                >
                  {isDeploying ? (
                    <>
                      <Spinner className="size-3.5 mr-2 animate-spin" />
                      Deploying...
                    </>
                  ) : (
                    <>
                      <Rocket className="size-3.5 mr-2" />
                      Deploy to Cloudflare
                    </>
                  )}
                </Button>
              </div>
            )}

            {/* Project list */}
            <div className="space-y-1">
              <p className="text-xs text-kumo-subtle font-medium">
                Your Projects
              </p>
              {isLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-10 rounded-lg bg-bg-3 dark:bg-kumo-elevated animate-pulse"
                    />
                  ))}
                </div>
              ) : chats && chats.length > 0 ? (
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {chats.map((chat) => (
                    <div
                      key={chat.id}
                      className={`flex items-center gap-2 p-2 rounded-lg transition-colors ${
                        chat.id === currentChatId
                          ? 'bg-orange-500/10 border border-orange-500/30'
                          : 'hover:bg-bg-3/50 dark:hover:bg-kumo-elevated/50'
                      }`}
                    >
                      <Code className="size-3.5 text-kumo-subtle shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-kumo-default truncate">
                          {chat.title}
                        </p>
                        <p className="text-[10px] text-kumo-subtle">
                          {chat.message_count} messages
                        </p>
                      </div>
                      {chat.id === currentChatId && (
                        <span className="text-[10px] text-orange-500 font-medium">
                          Current
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-kumo-subtle text-center py-2">
                  No projects yet
                </p>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
