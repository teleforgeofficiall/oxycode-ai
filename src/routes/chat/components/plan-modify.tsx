import React, { useState } from 'react';

interface PlanModifyProps {
  onSubmit: (modifications: string) => void;
  onCancel: () => void;
}

export default function PlanModify({ onSubmit, onCancel }: PlanModifyProps) {
  const [modifications, setModifications] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (modifications.trim()) {
      onSubmit(modifications.trim());
    }
  };

  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">✏️</span>
        <h2 className="text-xl font-bold text-gray-900">Modify Plan</h2>
      </div>

      <p className="text-gray-600 mb-4">
        Current plan mein kya changes chahiye? Describe karo in detail.
      </p>

      <form onSubmit={handleSubmit}>
        <textarea
          value={modifications}
          onChange={(e) => setModifications(e.target.value)}
          placeholder="Example: Add login page and remove payment folder. Also add dark mode support."
          className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        />

        <div className="flex gap-3 mt-4">
          <button
            type="submit"
            disabled={!modifications.trim()}
            className="flex-1 px-4 py-3 bg-blue-500 text-white font-semibold rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Submit Changes
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-3 bg-gray-200 text-gray-700 font-semibold rounded-lg hover:bg-gray-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
