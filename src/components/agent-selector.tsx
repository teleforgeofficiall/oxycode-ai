import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AGENT_TYPES } from '@/lib/agent-types';
import { CheckIcon } from '@phosphor-icons/react';

interface AgentSelectorProps {
  selected: string;
  onSelect: (agentId: string) => void;
}

export function AgentSelector({ selected, onSelect }: AgentSelectorProps) {
  const [expanded, setExpanded] = useState(false);
  const currentAgent = AGENT_TYPES.find((a) => a.id === selected) || AGENT_TYPES[0];

  return (
    <div className="w-full">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-kumo-line/50 bg-bg-3/30 hover:bg-bg-3/60 transition-all text-sm w-full"
      >
        <span className="text-lg">{currentAgent.icon}</span>
        <span className="font-medium text-kumo-default">{currentAgent.name}</span>
        <span className="text-kumo-subtle text-xs truncate flex-1 text-left">{currentAgent.description}</span>
        <svg
          className={`size-4 text-kumo-subtle transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-2 gap-2 mt-2">
              {AGENT_TYPES.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => {
                    onSelect(agent.id);
                    setExpanded(false);
                  }}
                  className={`relative flex flex-col items-start gap-1 p-3 rounded-xl border transition-all text-left ${
                    selected === agent.id
                      ? 'border-brand-emphasis/50 bg-brand-emphasis/5'
                      : 'border-kumo-line/50 bg-bg-3/20 hover:bg-bg-3/50 hover:border-kumo-line'
                  }`}
                >
                  <div className="flex items-center gap-2 w-full">
                    <span className="text-xl">{agent.icon}</span>
                    <span className="font-medium text-sm text-kumo-default">{agent.name}</span>
                    {selected === agent.id && (
                      <CheckIcon className="size-4 text-brand-emphasis ml-auto" weight="bold" />
                    )}
                  </div>
                  <p className="text-xs text-kumo-subtle leading-relaxed">{agent.description}</p>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
