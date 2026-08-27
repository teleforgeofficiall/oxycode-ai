// Main Agent - Orchestrator
// Manages sub-agents and coordinates tasks

import { 
  AgentType, 
  AgentStatus, 
  IntentType, 
  Task, 
  AgentResult, 
  SubAgent,
  MainAgentConfig,
  PlanData 
} from './types';
import { detectIntent, getAgentTypeForIntent } from './intentDetector';
import { PlannerAgent } from './plannerAgent';
import { BuildAgent } from './buildAgent';
import { ExploreAgent } from './exploreAgent';
import { DebugAgent } from './debugAgent';

export class MainAgent {
  private config: MainAgentConfig;
  private subAgents: Map<string, SubAgent> = new Map();
  private currentTask: Task | null = null;
  private conversationHistory: Array<{role: 'user' | 'assistant', content: string}> = [];
  private onProgress?: (progress: number, message: string) => void;
  private onPlanGenerated?: (plan: PlanData) => void;
  private onFileUpdate?: (files: any[]) => void;

  constructor(config: MainAgentConfig) {
    this.config = config;
  }

  setCallbacks(callbacks: {
    onProgress?: (progress: number, message: string) => void;
    onPlanGenerated?: (plan: PlanData) => void;
    onFileUpdate?: (files: any[]) => void;
  }) {
    this.onProgress = callbacks.onProgress;
    this.onPlanGenerated = callbacks.onPlanGenerated;
    this.onFileUpdate = callbacks.onFileUpdate;
  }

  async processMessage(message: string): Promise<AgentResult> {
    // Add user message to history
    this.conversationHistory.push({ role: 'user', content: message });

    // Detect intent
    const intent = detectIntent(message);
    this.reportProgress(10, `Intent detected: ${intent}`);

    // Create task
    const task: Task = {
      id: this.generateTaskId(),
      type: intent,
      description: message,
      context: {
        history: this.conversationHistory.slice(-5) // Last 5 messages for context
      }
    };

    this.currentTask = task;

    // Route to appropriate sub-agent
    const agentType = getAgentTypeForIntent(intent);
    this.reportProgress(20, `Creating ${agentType} agent...`);

    const subAgent = this.createSubAgent(agentType);
    this.subAgents.set(subAgent.id, subAgent);

    // Execute task
    this.reportProgress(30, `Executing ${intent} task...`);
    
    try {
      const result = await subAgent.execute(task);
      
      // Add assistant response to history
      if (result.success && result.data) {
        this.conversationHistory.push({ 
          role: 'assistant', 
          content: JSON.stringify(result.data) 
        });
      }

      this.reportProgress(100, 'Task completed!');
      return result;
    } catch (error) {
      this.reportProgress(100, 'Task failed!');
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  async approvePlan(): Promise<AgentResult> {
    if (!this.currentTask) {
      return { success: false, error: 'No current task' };
    }

    // Create build agent for code generation
    const buildAgent = this.createSubAgent('build');
    this.subAgents.set(buildAgent.id, buildAgent);

    this.reportProgress(10, 'Starting code generation...');

    // Execute build task
    const result = await buildAgent.execute({
      ...this.currentTask,
      type: 'create_project'
    });

    return result;
  }

  async rejectPlan(): Promise<AgentResult> {
    this.currentTask = null;
    this.subAgents.clear();
    
    return {
      success: true,
      data: { message: 'Plan rejected. Ready for new task.' }
    };
  }

  async modifyPlan(modifications: string): Promise<AgentResult> {
    if (!this.currentTask) {
      return { success: false, error: 'No current task' };
    }

    // Update task with modifications
    this.currentTask.modifications = modifications;

    // Create new planner agent
    const plannerAgent = this.createSubAgent('planner');
    this.subAgents.set(plannerAgent.id, plannerAgent);

    this.reportProgress(10, 'Updating plan with modifications...');

    // Generate new plan
    const result = await plannerAgent.execute({
      ...this.currentTask,
      description: `${this.currentTask.description}\n\nModifications: ${modifications}`
    });

    return result;
  }

  async handleFileOperation(operation: string): Promise<AgentResult> {
    const buildAgent = this.createSubAgent('build');
    this.subAgents.set(buildAgent.id, buildAgent);

    this.reportProgress(10, 'Processing file operation...');

    const result = await buildAgent.execute({
      id: this.generateTaskId(),
      type: 'file_operation',
      description: operation
    });

    return result;
  }

  private createSubAgent(type: AgentType): SubAgent {
    const id = this.generateSubAgentId(type);
    
    switch (type) {
      case 'planner':
        return new PlannerAgent(id, this.config);
      case 'build':
        return new BuildAgent(id, this.config);
      case 'explore':
        return new ExploreAgent(id, this.config);
      case 'debug':
        return new DebugAgent(id, this.config);
      default:
        throw new Error(`Unknown agent type: ${type}`);
    }
  }

  private reportProgress(progress: number, message: string) {
    if (this.onProgress) {
      this.onProgress(progress, message);
    }
  }

  private generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateSubAgentId(type: AgentType): string {
    return `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  getConversationHistory() {
    return this.conversationHistory;
  }

  getCurrentTask() {
    return this.currentTask;
  }

  getActiveSubAgents() {
    return Array.from(this.subAgents.values());
  }
}
