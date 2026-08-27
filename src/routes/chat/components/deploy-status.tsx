import React from 'react';

interface DeployStatusProps {
  status: 'connecting' | 'deploying' | 'deployed' | 'error';
  message: string;
  previewUrl?: string;
  error?: string;
  onConnect?: () => void;
}

export default function DeployStatus({ status, message, previewUrl, error, onConnect }: DeployStatusProps) {
  const getStatusIcon = () => {
    switch (status) {
      case 'connecting':
        return '🔗';
      case 'deploying':
        return '🚀';
      case 'deployed':
        return '✅';
      case 'error':
        return '❌';
      default:
        return '⏳';
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'connecting':
        return 'bg-yellow-50 border-yellow-200';
      case 'deploying':
        return 'bg-blue-50 border-blue-200';
      case 'deployed':
        return 'bg-green-50 border-green-200';
      case 'error':
        return 'bg-red-50 border-red-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className={`border rounded-lg p-4 ${getStatusColor()}`}>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl">{getStatusIcon()}</span>
        <div>
          <h3 className="font-semibold text-gray-900">Cloudflare Deployment</h3>
          <p className="text-sm text-gray-600">{message}</p>
        </div>
      </div>

      {/* Progress indicator for deploying state */}
      {status === 'deploying' && (
        <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
          <div className="bg-blue-500 h-2 rounded-full animate-pulse" style={{ width: '60%' }} />
        </div>
      )}

      {/* Success - Show preview URL */}
      {status === 'deployed' && previewUrl && (
        <div className="bg-green-100 p-3 rounded-lg">
          <p className="text-sm font-medium text-green-800 mb-2">Deployment Complete!</p>
          <div className="flex items-center gap-2">
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 underline font-mono text-sm"
            >
              {previewUrl}
            </a>
            <button
              onClick={() => navigator.clipboard.writeText(previewUrl)}
              className="px-2 py-1 bg-green-200 text-green-800 rounded text-xs hover:bg-green-300"
            >
              Copy
            </button>
          </div>
        </div>
      )}

      {/* Error - Show error message and connect button */}
      {status === 'error' && (
        <div className="space-y-3">
          <div className="bg-red-100 p-3 rounded-lg">
            <p className="text-sm text-red-800">{error || 'Deployment failed'}</p>
          </div>
          {onConnect && (
            <button
              onClick={onConnect}
              className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              🔗 Connect CF Account
            </button>
          )}
        </div>
      )}

      {/* No account connected */}
      {status === 'connecting' && !previewUrl && (
        <div className="bg-yellow-100 p-3 rounded-lg">
          <p className="text-sm text-yellow-800">
            Deploy karne ke liye apna CF account connect karein.
          </p>
        </div>
      )}
    </div>
  );
}
