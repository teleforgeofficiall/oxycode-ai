import React from 'react';

interface AgentProgressProps {
  agentType: string;
  progress: number;
  message: string;
}

export default function AgentProgress({ agentType, progress, message }: AgentProgressProps) {
  const getAgentIcon = () => {
    switch (agentType) {
      case 'planner':
        return '📋';
      case 'build':
        return '🔨';
      case 'explore':
        return '🔍';
      case 'debug':
        return '🐛';
      default:
        return '🤖';
    }
  };

  const getAgentName = () => {
    switch (agentType) {
      case 'planner':
        return 'Planner Agent';
      case 'build':
        return 'Build Agent';
      case 'explore':
        return 'Explore Agent';
      case 'debug':
        return 'Debug Agent';
      default:
        return 'AI Agent';
    }
  };

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl">{getAgentIcon()}</span>
        <div>
          <h3 className="font-semibold text-gray-900">{getAgentName()}</h3>
          <p className="text-sm text-gray-600">{message}</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      <p className="text-right text-sm text-gray-500 mt-1">{progress}%</p>
    </div>
  );
}
