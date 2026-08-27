import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { motion, AnimatePresence } from 'framer-motion';
import { PaperPlaneTiltIcon, ChatsIcon, TrashIcon, PencilSimpleIcon, ClockIcon } from '@phosphor-icons/react';
import { getChats, deleteChat, renameChat, type Chat } from '@/lib/chat-api';
import { AgentSelector } from '@/components/agent-selector';

const MAX_QUERY_LENGTH = 2000;

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function Home() {
  const navigate = useNavigate();
  const { user, isAuthenticated, isMaintenance, isAdmin } = useAuth();
  const [query, setQuery] = useState('');
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatsLoading, setChatsLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('oxygent');
  
  // Editable title state
  const [customTitle, setCustomTitle] = useState(() => 
    localStorage.getItem('oxycode_custom_title') || ''
  );
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitleInput, setEditTitleInput] = useState('');

  const handleSaveTitle = () => {
    const newTitle = editTitleInput.trim();
    setCustomTitle(newTitle);
    if (newTitle) {
      localStorage.setItem('oxycode_custom_title', newTitle);
    } else {
      localStorage.removeItem('oxycode_custom_title');
    }
    setIsEditingTitle(false);
  };

  const handleStartEditTitle = () => {
    setEditTitleInput(customTitle);
    setIsEditingTitle(true);
  };

  const handleCancelEditTitle = () => {
    setIsEditingTitle(false);
    setEditTitleInput('');
  };

  const placeholderPhrases = useMemo(
    () => ['a modern portfolio website', 'a Telegram bot', 'a SaaS landing page'],
    [],
  );

  useEffect(() => {
    if (isAuthenticated) {
      setChatsLoading(true);
      getChats()
        .then(setChats)
        .catch(console.error)
        .finally(() => setChatsLoading(false));
    }
  }, [isAuthenticated]);

  const handleCreateApp = () => {
    if (!query.trim() || query.length > MAX_QUERY_LENGTH) return;
    const encodedQuery = encodeURIComponent(query.trim());
    navigate(`/chat/new?query=${encodedQuery}&agent=${selectedAgent}`);
    setQuery('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCreateApp();
    }
  };

  const handleDeleteChat = async (e: React.MouseEvent, chatId: number) => {
    e.stopPropagation();
    if (!confirm('Delete this chat?')) return;
    try {
      await deleteChat(chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
  };

  const handleRenameChat = async (chatId: number) => {
    if (!editTitle.trim()) return;
    try {
      await renameChat(chatId, editTitle.trim());
      setChats((prev) =>
        prev.map((c) => (c.id === chatId ? { ...c, title: editTitle.trim() } : c)),
      );
      setEditingId(null);
    } catch (err) {
      console.error('Failed to rename chat:', err);
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
              <div className="flex items-center justify-center gap-2">
                {isEditingTitle ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editTitleInput}
                      onChange={(e) => setEditTitleInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveTitle();
                        if (e.key === 'Escape') handleCancelEditTitle();
                      }}
                      placeholder="Enter custom title..."
                      className="text-sm text-center bg-transparent border-b border-kumo-line focus:outline-none focus:border-brand-emphasis text-kumo-default px-2 py-1"
                      autoFocus
                    />
                    <button
                      onClick={handleSaveTitle}
                      className="text-xs text-brand-emphasis hover:text-brand-emphasis/80"
                    >
                      Save
                    </button>
                    <button
                      onClick={handleCancelEditTitle}
                      className="text-xs text-kumo-subtle hover:text-kumo-default"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <p 
                    className="text-center text-sm text-kumo-subtle cursor-pointer hover:text-kumo-default transition-colors group flex items-center gap-1"
                    onClick={handleStartEditTitle}
                  >
                    {customTitle ? (
                      <>
                        {customTitle}
                        <PencilSimpleIcon weight="duotone" className="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </>
                    ) : (
                      <>
                        Hey, {user.first_name} 👋
                        <PencilSimpleIcon weight="duotone" className="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </>
                    )}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="mb-3">
            <AgentSelector selected={selectedAgent} onSelect={setSelectedAgent} />
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

        {isAuthenticated && chats.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-12 mb-8"
          >
            <div className="flex items-center gap-2 mb-4">
              <ChatsIcon weight="duotone" className="size-4 text-kumo-subtle" />
              <h2 className="text-sm font-medium text-kumo-subtle">Recent Chats</h2>
            </div>

            <div className="grid gap-2">
              {chats.slice(0, 10).map((chat) => (
                <motion.div
                  key={chat.id}
                  layout
                  onClick={() => navigate(`/chat/${chat.id}`)}
                  className="group flex items-center gap-3 p-3 rounded-xl border border-kumo-line/50 bg-bg-3/30 hover:bg-bg-3/60 hover:border-kumo-line transition-all cursor-pointer"
                >
                  <div className="flex-1 min-w-0">
                    {editingId === chat.id ? (
                      <input
                        autoFocus
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={() => handleRenameChat(chat.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRenameChat(chat.id);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full bg-transparent border-b border-brand-emphasis text-sm text-kumo-default focus:outline-none"
                      />
                    ) : (
                      <p className="text-sm font-medium text-kumo-default truncate">
                        {chat.title}
                      </p>
                    )}
                    {chat.last_message && (
                      <p className="text-xs text-kumo-subtle truncate mt-0.5">
                        {chat.last_role === 'assistant' ? '🤖 ' : ''}
                        {chat.last_message}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingId(chat.id);
                        setEditTitle(chat.title);
                      }}
                      className="size-7 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-kumo-default hover:bg-bg-3 transition-colors"
                    >
                      <PencilSimpleIcon className="size-3.5" />
                    </button>
                    <button
                      onClick={(e) => handleDeleteChat(e, chat.id)}
                      className="size-7 rounded-lg flex items-center justify-center text-kumo-subtle hover:text-red-400 hover:bg-red-500/10"
                    >
                      <TrashIcon className="size-3.5" />
                    </button>
                  </div>

                  <div className="flex items-center gap-1 text-xs text-kumo-subtle shrink-0">
                    <ClockIcon className="size-3" />
                    <span>{formatTimeAgo(chat.updated_at)}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
