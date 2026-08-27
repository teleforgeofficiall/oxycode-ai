// Agent Types and Interfaces

export type AgentType = 'planner' | 'build' | 'explore' | 'debug';

export type AgentStatus = 'idle' | 'working' | 'completed' | 'failed';

export type IntentType = 
  | 'create_project'
  | 'modify_project'
  | 'fix_bug'
  | 'explore_code'
  | 'deploy'
  | 'chat'
  | 'file_operation';

export interface Task {
  id: string;
  type: IntentType;
  description: string;
  context?: any;
  files?: string[];
  modifications?: string;
}

export interface AgentResult {
  success: boolean;
  data?: any;
  error?: string;
  files?: FileInfo[];
  plan?: PlanData;
}

export interface FileInfo {
  path: string;
  content: string;
  action: 'create' | 'update' | 'delete';
}

export interface PlanData {
  overview: string;
  files: PlanFile[];
  folderStructure: string;
  estimatedTime: string;
}

export interface PlanFile {
  path: string;
  purpose: string;
  complexity: 'low' | 'medium' | 'high';
}

export interface SubAgent {
  id: string;
  type: AgentType;
  status: AgentStatus;
  execute: (task: Task) => Promise<AgentResult>;
  reportProgress: (progress: number, message: string) => void;
  getResult: () => AgentResult;
}

export interface MainAgentConfig {
  apiKey: string;
  model?: string;
  maxTokens?: number;
}
