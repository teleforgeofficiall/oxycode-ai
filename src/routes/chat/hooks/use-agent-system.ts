import { useState, useCallback, useRef } from 'react';
import { PlanData, AgentResult } from '../../../worker/agents/types';

interface AgentState {
  // Agent status
  isAgentActive: boolean;
  currentAgentType: string | null;
  agentProgress: number;
  agentMessage: string;

  // Plan state
  currentPlan: PlanData | null;
  planStatus: 'pending' | 'approved' | 'rejected' | 'modified';
  isPlanApprovalRequired: boolean;

  // File operation state
  pendingFileOperation: {
    type: 'delete' | 'edit' | 'recreate';
    filePath: string;
    message: string;
  } | null;

  // Deployment state
  deploymentStatus: 'idle' | 'connecting' | 'deploying' | 'deployed' | 'error';
  deploymentMessage: string;
  previewUrl: string | null;
  deploymentError: string | null;

  // Messages
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
}

export function useAgentSystem() {
  const [state, setState] = useState<AgentState>({
    isAgentActive: false,
    currentAgentType: null,
    agentProgress: 0,
    agentMessage: '',
    currentPlan: null,
    planStatus: 'pending',
    isPlanApprovalRequired: false,
    pendingFileOperation: null,
    deploymentStatus: 'idle',
    deploymentMessage: '',
    previewUrl: null,
    deploymentError: null,
    messages: []
  });

  const websocketRef = useRef<WebSocket | null>(null);

  // Send message to backend
  const sendMessage = useCallback((message: string) => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'user_message',
        content: message
      }));
    }

    // Add user message to state
    setState(prev => ({
      ...prev,
      messages: [...prev.messages, { role: 'user', content: message }]
    }));
  }, []);

  // Approve plan
  const approvePlan = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'plan_approval',
        action: 'approve'
      }));
    }

    setState(prev => ({
      ...prev,
      planStatus: 'approved',
      isPlanApprovalRequired: false
    }));
  }, []);

  // Reject plan
  const rejectPlan = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'plan_approval',
        action: 'reject'
      }));
    }

    setState(prev => ({
      ...prev,
      planStatus: 'rejected',
      isPlanApprovalRequired: false,
      currentPlan: null
    }));
  }, []);

  // Modify plan
  const modifyPlan = useCallback((modifications: string) => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'plan_approval',
        action: 'modify',
        modifications
      }));
    }

    setState(prev => ({
      ...prev,
      planStatus: 'modified'
    }));
  }, []);

  // Confirm file operation
  const confirmFileOperation = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'file_operation_confirm',
        confirmed: true
      }));
    }

    setState(prev => ({
      ...prev,
      pendingFileOperation: null
    }));
  }, []);

  // Cancel file operation
  const cancelFileOperation = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'file_operation_confirm',
        confirmed: false
      }));
    }

    setState(prev => ({
      ...prev,
      pendingFileOperation: null
    }));
  }, []);

  // Connect to CF
  const connectCloudflare = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'deploy',
        action: 'connect'
      }));
    }
  }, []);

  // Deploy to CF
  const deployToCloudflare = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'deploy',
        action: 'deploy'
      }));
    }
  }, []);

  // Handle WebSocket message
  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'agent_progress':
          setState(prev => ({
            ...prev,
            isAgentActive: true,
            currentAgentType: data.agentType,
            agentProgress: data.progress,
            agentMessage: data.message
          }));
          break;

        case 'plan_generated':
          setState(prev => ({
            ...prev,
            currentPlan: data.plan,
            isPlanApprovalRequired: true,
            planStatus: 'pending'
          }));
          break;

        case 'plan_approval_required':
          setState(prev => ({
            ...prev,
            isPlanApprovalRequired: true,
            planStatus: 'pending'
          }));
          break;

        case 'plan_approved':
          setState(prev => ({
            ...prev,
            planStatus: 'approved',
            isPlanApprovalRequired: false,
            isAgentActive: true,
            currentAgentType: 'build'
          }));
          break;

        case 'plan_rejected':
          setState(prev => ({
            ...prev,
            planStatus: 'rejected',
            isPlanApprovalRequired: false,
            currentPlan: null,
            isAgentActive: false
          }));
          break;

        case 'plan_modified':
          setState(prev => ({
            ...prev,
            planStatus: 'modified'
          }));
          break;

        case 'file_operation_confirm':
          setState(prev => ({
            ...prev,
            pendingFileOperation: {
              type: data.operation,
              filePath: data.filePath,
              message: data.message
            }
          }));
          break;

        case 'file_operation_complete':
          setState(prev => ({
            ...prev,
            pendingFileOperation: null
          }));
          break;

        case 'deployment_status':
          setState(prev => ({
            ...prev,
            deploymentStatus: data.status,
            deploymentMessage: data.message,
            previewUrl: data.previewUrl || null,
            deploymentError: data.error || null
          }));
          break;

        case 'assistant_message':
          setState(prev => ({
            ...prev,
            messages: [...prev.messages, { role: 'assistant', content: data.content }]
          }));
          break;

        case 'generation_complete':
          setState(prev => ({
            ...prev,
            isAgentActive: false,
            currentAgentType: null,
            agentProgress: 100,
            agentMessage: 'Complete!'
          }));
          break;
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }, []);

  // Connect WebSocket
  const connectWebSocket = useCallback((url: string) => {
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
    };
    
    ws.onmessage = handleWebSocketMessage;
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };
    
    websocketRef.current = ws;
    
    return () => {
      ws.close();
    };
  }, [handleWebSocketMessage]);

  return {
    state,
    actions: {
      sendMessage,
      approvePlan,
      rejectPlan,
      modifyPlan,
      confirmFileOperation,
      cancelFileOperation,
      connectCloudflare,
      deployToCloudflare,
      connectWebSocket
    }
  };
}
