// Sub-Agent Manager
// Manages creation and lifecycle of sub-agents

import { AgentType, AgentStatus, Task, AgentResult, SubAgent, MainAgentConfig } from './types';
import { PlannerAgent } from './plannerAgent';
import { BuildAgent } from './buildAgent';
import { ExploreAgent } from './exploreAgent';
import { DebugAgent } from './debugAgent';

export class SubAgentManager {
  private agents: Map<string, SubAgent> = new Map();
  private config: MainAgentConfig;
  private onAgentProgress?: (agentId: string, progress: number, message: string) => void;
  private onAgentComplete?: (agentId: string, result: AgentResult) => void;
  private onAgentFailed?: (agentId: string, error: string) => void;

  constructor(config: MainAgentConfig) {
    this.config = config;
  }

  setCallbacks(callbacks: {
    onAgentProgress?: (agentId: string, progress: number, message: string) => void;
    onAgentComplete?: (agentId: string, result: AgentResult) => void;
    onAgentFailed?: (agentId: string, error: string) => void;
  }) {
    this.onAgentProgress = callbacks.onAgentProgress;
    this.onAgentComplete = callbacks.onAgentComplete;
    this.onAgentFailed = callbacks.onAgentFailed;
  }

  createAgent(type: AgentType): SubAgent {
    const id = this.generateAgentId(type);
    let agent: SubAgent;

    switch (type) {
      case 'planner':
        agent = new PlannerAgent(id, this.config);
        break;
      case 'build':
        agent = new BuildAgent(id, this.config);
        break;
      case 'explore':
        agent = new ExploreAgent(id, this.config);
        break;
      case 'debug':
        agent = new DebugAgent(id, this.config);
        break;
      default:
        throw new Error(`Unknown agent type: ${type}`);
    }

    // Set up progress callbacks
    agent.reportProgress = (progress: number, message: string) => {
      this.onAgentProgress?.(id, progress, message);
    };

    this.agents.set(id, agent);
    return agent;
  }

  async executeAgent(agentId: string, task: Task): Promise<AgentResult> {
    const agent = this.agents.get(agentId);
    if (!agent) {
      return {
        success: false,
        error: `Agent ${agentId} not found`
      };
    }

    try {
      const result = await agent.execute(task);
      
      if (result.success) {
        this.onAgentComplete?.(agentId, result);
      } else {
        this.onAgentFailed?.(agentId, result.error || 'Unknown error');
      }
      
      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      this.onAgentFailed?.(agentId, errorMessage);
      
      return {
        success: false,
        error: errorMessage
      };
    }
  }

  getAgent(agentId: string): SubAgent | undefined {
    return this.agents.get(agentId);
  }

  getAllAgents(): SubAgent[] {
    return Array.from(this.agents.values());
  }

  getActiveAgents(): SubAgent[] {
    return Array.from(this.agents.values()).filter(
      agent => agent.status === 'working'
    );
  }

  getAgentsByType(type: AgentType): SubAgent[] {
    return Array.from(this.agents.values()).filter(
      agent => agent.type === type
    );
  }

  removeAgent(agentId: string): boolean {
    return this.agents.delete(agentId);
  }

  clearAllAgents(): void {
    this.agents.clear();
  }

  getAgentStatus(agentId: string): AgentStatus | undefined {
    return this.agents.get(agentId)?.status;
  }

  private generateAgentId(type: AgentType): string {
    return `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}
