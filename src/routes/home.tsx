import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { motion } from 'framer-motion';
import { PaperPlaneTiltIcon } from '@phosphor-icons/react';

const MAX_QUERY_LENGTH = 2000;

export default function Home() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [query, setQuery] = useState('');

  const placeholderPhrases = useMemo(
    () => ['a modern portfolio website', 'a Telegram bot', 'a SaaS landing page'],
    [],
  );

  const handleCreateApp = () => {
    if (!query.trim() || query.length > MAX_QUERY_LENGTH) return;

    const encodedQuery = encodeURIComponent(query.trim());
    navigate(`/chat/new?query=${encodedQuery}`);
    setQuery('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCreateApp();
    }
  };

  return (
    <div className="relative flex flex-col items-center w-full min-h-full">
      <title>OXYCODE AI</title>
      <div className="home-atmosphere" aria-hidden>
        <div className="home-atmosphere__spotlight" />
      </div>

      <div className="w-full max-w-3xl px-5 sm:px-6">
        <motion.div
          layout
          transition={{
            layout: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
          }}
          className="flex flex-col items-stretch z-10 w-full mt-[18vh] sm:mt-[22vh] md:mt-[26vh]"
        >
          <div className="mb-6 sm:mb-7 grid gap-2">
            <h1 className="w-full text-center text-[clamp(1.75rem,4.5vw,2.5rem)] font-semibold leading-[1.12] text-kumo-strong/80 z-20">
              What do you want to{' '}
              <span className="font-bold text-[1.1em] tracking-tighter uppercase text-brand-emphasis">
                build
              </span>
              ?
            </h1>
            {user && (
              <p className="text-center text-sm text-kumo-subtle">
                Hey, {user.first_name} 👋
              </p>
            )}
          </div>

          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe what you want to build..."
              rows={3}
              className="w-full rounded-xl border border-kumo-line bg-bg-3/50 px-4 py-3 pr-12 text-sm text-kumo-default placeholder:text-kumo-subtle resize-none focus:outline-none focus:ring-2 focus:ring-brand-emphasis/50"
            />
            <button
              onClick={handleCreateApp}
              disabled={!query.trim()}
              className="absolute right-3 bottom-3 size-9 rounded-lg bg-brand-emphasis text-white flex items-center justify-center disabled:opacity-50 hover:bg-brand-emphasis/90 transition-colors"
            >
              <PaperPlaneTiltIcon weight="duotone" className="size-4" />
            </button>
          </div>

          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-kumo-subtle">
            <span>
              {query.length}/{MAX_QUERY_LENGTH}
            </span>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
