import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PaperPlaneTiltIcon,
  RobotIcon,
  UserIcon,
  SpinnerIcon,
  WarningCircleIcon,
  ArrowSquareOutIcon,
} from '@phosphor-icons/react';
import { apiClient } from '@/lib/api-client';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  model?: string;
  timestamp: Date;
}

export default function Home() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (token) apiClient.setToken(token);
  }, [token]);

  const handleSubmit = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await apiClient.sendMessage({ message: text });
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: res.response,
        model: res.model,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setRemaining(res.remaining);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'error',
        content: err?.message || 'Something went wrong. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="relative flex flex-col h-full w-full overflow-hidden">
      <title>OXYCODE AI</title>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-center max-w-lg"
            >
              <div className="mb-4 inline-flex size-16 items-center justify-center rounded-2xl bg-brand-emphasis/10">
                <RobotIcon weight="duotone" className="size-8 text-brand-emphasis" />
              </div>
              <h1 className="text-2xl font-semibold text-kumo-strong mb-2">
                Hey, {user?.first_name || 'there'} 👋
              </h1>
              <p className="text-sm text-kumo-subtle mb-6">
                Describe what you want to build and I'll create it for you.
              </p>

              {/* Quick suggestions */}
              <div className="flex flex-wrap justify-center gap-2">
                {[
                  'A modern portfolio website',
                  'A Telegram bot',
                  'A SaaS landing page',
                  'A REST API with auth',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      setInput(suggestion);
                      textareaRef.current?.focus();
                    }}
                    className="rounded-lg border border-kumo-line bg-bg-3/50 px-3 py-1.5 text-xs text-kumo-subtle hover:bg-bg-3 hover:text-kumo-default transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </motion.div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            <AnimatePresence mode="popLayout">
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role !== 'user' && (
                    <div
                      className={`shrink-0 size-8 rounded-lg flex items-center justify-center ${
                        msg.role === 'error'
                          ? 'bg-red-500/10'
                          : 'bg-brand-emphasis/10'
                      }`}
                    >
                      {msg.role === 'error' ? (
                        <WarningCircleIcon weight="duotone" className="size-4 text-red-400" />
                      ) : (
                        <RobotIcon weight="duotone" className="size-4 text-brand-emphasis" />
                      )}
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-brand-emphasis text-white'
                        : msg.role === 'error'
                          ? 'bg-red-500/10 text-red-300 border border-red-500/20'
                          : 'bg-bg-3 border border-kumo-line text-kumo-default'
                    }`}
                  >
                    <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                    {msg.model && (
                      <div className="mt-2 text-[10px] text-kumo-subtle opacity-60">
                        {msg.model}
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="shrink-0 size-8 rounded-lg bg-bg-3 flex items-center justify-center">
                      <UserIcon weight="duotone" className="size-4 text-kumo-subtle" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Loading indicator */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-3"
              >
                <div className="size-8 rounded-lg bg-brand-emphasis/10 flex items-center justify-center">
                  <SpinnerIcon weight="duotone" className="size-4 text-brand-emphasis animate-spin" />
                </div>
                <div className="bg-bg-3 border border-kumo-line rounded-xl px-4 py-3 text-sm text-kumo-subtle">
                  Thinking...
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-kumo-line bg-bg-2/80 backdrop-blur-sm px-4 py-3">
        <div className="max-w-3xl mx-auto">
          {remaining !== null && (
            <div className="mb-2 text-[11px] text-kumo-subtle text-center">
              {remaining} messages remaining
            </div>
          )}
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe what you want to build..."
              rows={2}
              disabled={isLoading}
              className="w-full rounded-xl border border-kumo-line bg-bg-3/50 px-4 py-3 pr-12 text-sm text-kumo-default placeholder:text-kumo-subtle resize-none focus:outline-none focus:ring-2 focus:ring-brand-emphasis/50 disabled:opacity-50"
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isLoading}
              className="absolute right-3 bottom-3 size-9 rounded-lg bg-brand-emphasis text-white flex items-center justify-center disabled:opacity-50 hover:bg-brand-emphasis/90 transition-colors"
            >
              {isLoading ? (
                <SpinnerIcon weight="duotone" className="size-4 animate-spin" />
              ) : (
                <PaperPlaneTiltIcon weight="duotone" className="size-4" />
              )}
            </button>
          </div>
          <div className="mt-1.5 text-[10px] text-kumo-subtle text-center">
            Press Enter to send, Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  );
}
