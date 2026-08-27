import React from 'react';

interface ConfirmationDialogProps {
  operation: 'delete' | 'edit' | 'recreate';
  filePath: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmationDialog({
  operation,
  filePath,
  message,
  onConfirm,
  onCancel
}: ConfirmationDialogProps) {
  const getIcon = () => {
    switch (operation) {
      case 'delete':
        return '🗑️';
      case 'edit':
        return '✏️';
      case 'recreate':
        return '🔄';
      default:
        return '⚠️';
    }
  };

  const getTitle = () => {
    switch (operation) {
      case 'delete':
        return 'Confirm Delete';
      case 'edit':
        return 'Confirm Edit';
      case 'recreate':
        return 'Confirm Recreate';
      default:
        return 'Confirm Action';
    }
  };

  const getButtonColor = () => {
    switch (operation) {
      case 'delete':
        return 'bg-red-500 hover:bg-red-600';
      case 'edit':
        return 'bg-blue-500 hover:bg-blue-600';
      case 'recreate':
        return 'bg-yellow-500 hover:bg-yellow-600';
      default:
        return 'bg-gray-500 hover:bg-gray-600';
    }
  };

  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">{getIcon()}</span>
        <h2 className="text-xl font-bold text-gray-900">{getTitle()}</h2>
      </div>

      <div className="mb-4">
        <p className="text-gray-600 mb-2">{message}</p>
        <div className="bg-gray-50 p-3 rounded-lg">
          <p className="text-sm font-medium text-gray-700">File:</p>
          <p className="text-gray-900 font-mono">{filePath}</p>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onConfirm}
          className={`flex-1 px-4 py-3 text-white font-semibold rounded-lg transition-colors ${getButtonColor()}`}
        >
          {operation === 'delete' ? '✅ Yes, Delete' : 
           operation === 'edit' ? '✅ Yes, Edit' : 
           '✅ Yes, Recreate'}
        </button>
        <button
          onClick={onCancel}
          className="flex-1 px-4 py-3 bg-gray-200 text-gray-700 font-semibold rounded-lg hover:bg-gray-300 transition-colors"
        >
          ❌ Cancel
        </button>
      </div>
    </div>
  );
}
