import React from 'react';
import { PlanData } from '../../worker/agents/types';

interface PlanDisplayProps {
  plan: PlanData;
  onApprove: () => void;
  onReject: () => void;
  onModify: () => void;
}

export default function PlanDisplay({ plan, onApprove, onReject, onModify }: PlanDisplayProps) {
  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">📋</span>
        <h2 className="text-xl font-bold text-gray-900">Project Plan</h2>
      </div>

      {/* Overview */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Overview</h3>
        <p className="text-gray-600 whitespace-pre-wrap">{plan.overview}</p>
      </div>

      {/* File Structure */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">File Structure</h3>
        <pre className="bg-gray-50 p-4 rounded-lg text-sm font-mono text-gray-800 overflow-x-auto">
          {plan.folderStructure}
        </pre>
      </div>

      {/* Files List */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Files to Create</h3>
        <div className="space-y-2">
          {plan.files.map((file, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <span className="text-gray-500">📄</span>
                <div>
                  <p className="font-medium text-gray-900">{file.path}</p>
                  <p className="text-sm text-gray-500">{file.purpose}</p>
                </div>
              </div>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                file.complexity === 'high' ? 'bg-red-100 text-red-700' :
                file.complexity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                'bg-green-100 text-green-700'
              }`}>
                {file.complexity}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-6 text-sm text-gray-600">
        <span>📁 {plan.files.length} files</span>
        <span>⏱️ {plan.estimatedTime}</span>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <button
          onClick={onApprove}
          className="flex-1 px-4 py-3 bg-green-500 text-white font-semibold rounded-lg hover:bg-green-600 transition-colors"
        >
          ✅ Approve
        </button>
        <button
          onClick={onReject}
          className="flex-1 px-4 py-3 bg-red-500 text-white font-semibold rounded-lg hover:bg-red-600 transition-colors"
        >
          ❌ Reject
        </button>
        <button
          onClick={onModify}
          className="flex-1 px-4 py-3 bg-blue-500 text-white font-semibold rounded-lg hover:bg-blue-600 transition-colors"
        >
          ✏️ Modify
        </button>
      </div>
    </div>
  );
}
