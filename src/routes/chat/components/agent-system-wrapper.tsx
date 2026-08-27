import React, { useState, useEffect, useCallback } from 'react';
import { PlanDisplay } from './plan-display';
import { PlanModify } from './plan-modify';
import { ConfirmationDialog } from './confirmation-dialog';
import { AgentProgress } from './agent-progress';
import { DeployStatus } from './deploy-status';

interface AgentSystemWrapperProps {
  children: React.ReactNode;
  onSendMessage: (message: string) => void;
}

interface AgentState {
  isActive: boolean;
  agentType: string | null;
  progress: number;
  message: string;
  currentPlan: any | null;
  planStatus: 'pending' | 'approved' | 'rejected' | 'modified';
  showPlanApproval: boolean;
  showModifyInput: boolean;
  pendingFileOperation: any | null;
  deploymentStatus: 'idle' | 'connecting' | 'deploying' | 'deployed' | 'error';
  deploymentMessage: string;
  previewUrl: string | null;
  deploymentError: string | null;
}

export default function AgentSystemWrapper({ 
  children, 
  onSendMessage 
}: AgentSystemWrapperProps) {
  const [agentState, setAgentState] = useState<AgentState>({
    isActive: false,
    agentType: null,
    progress: 0,
    message: '',
    currentPlan: null,
    planStatus: 'pending',
    showPlanApproval: false,
    showModifyInput: false,
    pendingFileOperation: null,
    deploymentStatus: 'idle',
    deploymentMessage: '',
    previewUrl: null,
    deploymentError: null
  });

  // Handle plan approval
  const handleApprovePlan = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      planStatus: 'approved',
      showPlanApproval: false
    }));
    // Send approval to backend
    onSendMessage('__PLAN_APPROVED__');
  }, [onSendMessage]);

  // Handle plan rejection
  const handleRejectPlan = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      planStatus: 'rejected',
      showPlanApproval: false,
      currentPlan: null
    }));
    // Send rejection to backend
    onSendMessage('__PLAN_REJECTED__');
  }, [onSendMessage]);

  // Handle plan modification
  const handleModifyPlan = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      showModifyInput: true
    }));
  }, []);

  // Submit modifications
  const handleSubmitModifications = useCallback((modifications: string) => {
    setAgentState(prev => ({
      ...prev,
      showModifyInput: false,
      planStatus: 'modified'
    }));
    // Send modifications to backend
    onSendMessage(`__PLAN_MODIFY__: ${modifications}`);
  }, [onSendMessage]);

  // Cancel modification
  const handleCancelModify = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      showModifyInput: false
    }));
  }, []);

  // Confirm file operation
  const handleConfirmFileOperation = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      pendingFileOperation: null
    }));
    // Send confirmation to backend
    onSendMessage('__FILE_OP_CONFIRMED__');
  }, [onSendMessage]);

  // Cancel file operation
  const handleCancelFileOperation = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      pendingFileOperation: null
    }));
    // Send cancellation to backend
    onSendMessage('__FILE_OP_CANCELLED__');
  }, [onSendMessage]);

  // Connect to Cloudflare
  const handleConnectCloudflare = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      deploymentStatus: 'connecting',
      deploymentMessage: 'Connecting to Cloudflare...'
    }));
    // Send connect request to backend
    onSendMessage('__CF_CONNECT__');
  }, [onSendMessage]);

  // Deploy to Cloudflare
  const handleDeploy = useCallback(() => {
    setAgentState(prev => ({
      ...prev,
      deploymentStatus: 'deploying',
      deploymentMessage: 'Deploying to Cloudflare...'
    }));
    // Send deploy request to backend
    onSendMessage('__CF_DEPLOY__');
  }, [onSendMessage]);

  // Simulate WebSocket messages for demo
  useEffect(() => {
    // This would be replaced with actual WebSocket connection
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'agent_progress':
            setAgentState(prev => ({
              ...prev,
              isActive: true,
              agentType: data.agentType,
              progress: data.progress,
              message: data.message
            }));
            break;

          case 'plan_generated':
            setAgentState(prev => ({
              ...prev,
              currentPlan: data.plan,
              showPlanApproval: true,
              planStatus: 'pending'
            }));
            break;

          case 'plan_approved':
            setAgentState(prev => ({
              ...prev,
              planStatus: 'approved',
              showPlanApproval: false,
              isActive: true,
              agentType: 'build'
            }));
            break;

          case 'plan_rejected':
            setAgentState(prev => ({
              ...prev,
              planStatus: 'rejected',
              showPlanApproval: false,
              currentPlan: null,
              isActive: false
            }));
            break;

          case 'file_operation_confirm':
            setAgentState(prev => ({
              ...prev,
              pendingFileOperation: {
                type: data.operation,
                filePath: data.filePath,
                message: data.message
              }
            }));
            break;

          case 'deployment_status':
            setAgentState(prev => ({
              ...prev,
              deploymentStatus: data.status,
              deploymentMessage: data.message,
              previewUrl: data.previewUrl || null,
              deploymentError: data.error || null
            }));
            break;

          case 'generation_complete':
            setAgentState(prev => ({
              ...prev,
              isActive: false,
              agentType: null,
              progress: 100,
              message: 'Complete!'
            }));
            break;
        }
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };

    // Cleanup
    return () => {
      // Remove event listener
    };
  }, []);

  return (
    <div className="relative">
      {/* Agent Progress Indicator */}
      {agentState.isActive && (
        <div className="mb-4">
          <AgentProgress
            agentType={agentState.agentType || 'main'}
            progress={agentState.progress}
            message={agentState.message}
          />
        </div>
      )}

      {/* Plan Display */}
      {agentState.showPlanApproval && agentState.currentPlan && (
        <div className="mb-4">
          <PlanDisplay
            plan={agentState.currentPlan}
            onApprove={handleApprovePlan}
            onReject={handleRejectPlan}
            onModify={handleModifyPlan}
          />
        </div>
      )}

      {/* Plan Modification Input */}
      {agentState.showModifyInput && (
        <div className="mb-4">
          <PlanModify
            onSubmit={handleSubmitModifications}
            onCancel={handleCancelModify}
          />
        </div>
      )}

      {/* File Operation Confirmation */}
      {agentState.pendingFileOperation && (
        <div className="mb-4">
          <ConfirmationDialog
            operation={agentState.pendingFileOperation.type}
            filePath={agentState.pendingFileOperation.filePath}
            message={agentState.pendingFileOperation.message}
            onConfirm={handleConfirmFileOperation}
            onCancel={handleCancelFileOperation}
          />
        </div>
      )}

      {/* Deployment Status */}
      {agentState.deploymentStatus !== 'idle' && (
        <div className="mb-4">
          <DeployStatus
            status={agentState.deploymentStatus}
            message={agentState.deploymentMessage}
            previewUrl={agentState.previewUrl || undefined}
            error={agentState.deploymentError || undefined}
            onConnect={handleConnectCloudflare}
          />
        </div>
      )}

      {/* Main Content */}
      {children}
    </div>
  );
}
