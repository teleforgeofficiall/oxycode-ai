// Agent System Controller
// Handles multi-agent system with planner, build, explore, debug agents

import { BaseController } from '../baseController';
import { RouteContext } from '../../types/route-context';
import { createLogger } from '../../../logger';
import { MainAgent, detectIntent, getAgentTypeForIntent } from '../../../agents';
import { PlanData, AgentResult } from '../../../agents/types';

interface AgentSession {
  id: string;
  mainAgent: MainAgent;
  userId: string;
  status: 'active' | 'completed' | 'failed';
  createdAt: Date;
  currentPlan: PlanData | null;
  planStatus: 'pending' | 'approved' | 'rejected' | 'modified';
}

export class AgentSystemController extends BaseController {
  private static logger = createLogger('AgentSystemController');
  private static sessions: Map<string, AgentSession> = new Map();

  /**
   * Create a new agent session
   */
  static async createSession(
    request: Request,
    env: Env,
    _: ExecutionContext,
    context: RouteContext
  ): Promise<Response> {
    try {
      const user = context.user!;
      const body = await request.json() as { query: string };
      
      if (!body.query || body.query.trim().length === 0) {
        return this.createErrorResponse('Query is required', 400);
      }

      // Create main agent
      const mainAgent = new MainAgent({
        apiKey: env.OPENAI_API_KEY || '',
        model: 'gpt-4'
      });

      // Set up callbacks
      mainAgent.setCallbacks({
        onProgress: (progress, message) => {
          // This will be sent via WebSocket
          this.logger.info(`Agent progress: ${progress}% - ${message}`);
        },
        onPlanGenerated: (plan) => {
          this.logger.info('Plan generated', { fileCount: plan.files.length });
        }
      });

      // Create session
      const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const session: AgentSession = {
        id: sessionId,
        mainAgent,
        userId: user.id,
        status: 'active',
        createdAt: new Date(),
        currentPlan: null,
        planStatus: 'pending'
      };

      this.sessions.set(sessionId, session);

      // Process the initial message
      const result = await mainAgent.processMessage(body.query);

      // Update session with plan if generated
      if (result.success && result.plan) {
        session.currentPlan = result.plan;
      }

      return new Response(JSON.stringify({
        success: true,
        sessionId,
        result
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      this.logger.error('Error creating agent session', error);
      return this.createErrorResponse(error, 500);
    }
  }

  /**
   * Handle WebSocket connections for agent system
   */
  static async handleWebSocketConnection(
    request: Request,
    env: Env,
    _: ExecutionContext,
    context: RouteContext
  ): Promise<Response> {
    try {
      const sessionId = context.pathParams.sessionId;
      if (!sessionId) {
        return this.createErrorResponse('Missing session ID', 400);
      }

      // Ensure the request is a WebSocket upgrade request
      if (request.headers.get('Upgrade') !== 'websocket') {
        return new Response('Expected WebSocket upgrade', { status: 426 });
      }

      const user = context.user!;
      const session = this.sessions.get(sessionId);

      if (!session) {
        return this.createErrorResponse('Session not found', 404);
      }

      if (session.userId !== user.id) {
        return this.createErrorResponse('Unauthorized', 403);
      }

      // Create WebSocket pair
      const { 0: client, 1: server } = new WebSocketPair();
      server.accept();

      // Send initial state
      server.send(JSON.stringify({
        type: 'session_connected',
        sessionId,
        status: session.status,
        currentPlan: session.currentPlan,
        planStatus: session.planStatus
      }));

      // Handle WebSocket messages
      server.addEventListener('message', async (event) => {
        try {
          const data = JSON.parse(event.data as string);
          await this.handleWebSocketMessage(server, session, data, env);
        } catch (error) {
          this.logger.error('Error handling WebSocket message', error);
          server.send(JSON.stringify({
            type: 'error',
            error: 'Invalid message format'
          }));
        }
      });

      server.addEventListener('close', () => {
        this.logger.info(`WebSocket closed for session ${sessionId}`);
      });

      return new Response(null, {
        status: 101,
        webSocket: client
      });

    } catch (error) {
      this.logger.error('Error handling WebSocket connection', error);
      return this.createErrorResponse(error, 500);
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private static async handleWebSocketMessage(
    server: WebSocket,
    session: AgentSession,
    data: any,
    env: Env
  ): Promise<void> {
    const { type } = data;

    switch (type) {
      case 'user_message':
        await this.handleUserMessage(server, session, data.content);
        break;

      case 'plan_approval':
        await this.handlePlanApproval(server, session, data);
        break;

      case 'file_operation_confirm':
        await this.handleFileOperationConfirm(server, session, data);
        break;

      case 'deploy':
        await this.handleDeploy(server, session, data, env);
        break;

      default:
        server.send(JSON.stringify({
          type: 'error',
          error: `Unknown message type: ${type}`
        }));
    }
  }

  /**
   * Handle user message
   */
  private static async handleUserMessage(
    server: WebSocket,
    session: AgentSession,
    content: string
  ): Promise<void> {
    // Send progress
    server.send(JSON.stringify({
      type: 'agent_progress',
      agentType: 'main',
      progress: 10,
      message: 'Processing your message...'
    }));

    // Process message with main agent
    const result = await session.mainAgent.processMessage(content);

    if (result.success) {
      // Check if plan was generated
      if (result.plan) {
        session.currentPlan = result.plan;
        session.planStatus = 'pending';

        // Send plan to client
        server.send(JSON.stringify({
          type: 'plan_generated',
          plan: result.plan
        }));

        server.send(JSON.stringify({
          type: 'plan_approval_required',
          planId: session.id,
          message: 'Please review the plan'
        }));
      } else {
        // Send regular response
        server.send(JSON.stringify({
          type: 'assistant_message',
          content: result.data?.message || 'Task completed'
        }));
      }
    } else {
      server.send(JSON.stringify({
        type: 'error',
        error: result.error || 'Failed to process message'
      }));
    }

    // Send completion
    server.send(JSON.stringify({
      type: 'agent_progress',
      agentType: 'main',
      progress: 100,
      message: 'Complete'
    }));
  }

  /**
   * Handle plan approval
   */
  private static async handlePlanApproval(
    server: WebSocket,
    session: AgentSession,
    data: any
  ): Promise<void> {
    const { action, modifications } = data;

    switch (action) {
      case 'approve':
        session.planStatus = 'approved';
        
        server.send(JSON.stringify({
          type: 'plan_approved',
          planId: session.id,
          message: 'Plan approved! Starting code generation...'
        }));

        // Start build process
        await this.startBuildProcess(server, session);
        break;

      case 'reject':
        session.planStatus = 'rejected';
        session.currentPlan = null;

        server.send(JSON.stringify({
          type: 'plan_rejected',
          planId: session.id,
          message: 'Plan rejected. Ready for new task.'
        }));
        break;

      case 'modify':
        session.planStatus = 'modified';

        server.send(JSON.stringify({
          type: 'agent_progress',
          agentType: 'planner',
          progress: 10,
          message: 'Updating plan with modifications...'
        }));

        // Get modified plan
        const result = await session.mainAgent.modifyPlan(modifications);

        if (result.success && result.plan) {
          session.currentPlan = result.plan;
          session.planStatus = 'pending';

          server.send(JSON.stringify({
            type: 'plan_generated',
            plan: result.plan
          }));

          server.send(JSON.stringify({
            type: 'plan_approval_required',
            planId: session.id,
            message: 'Updated plan ready for review'
          }));
        } else {
          server.send(JSON.stringify({
            type: 'error',
            error: result.error || 'Failed to modify plan'
          }));
        }
        break;
    }
  }

  /**
   * Start build process
   */
  private static async startBuildProcess(
    server: WebSocket,
    session: AgentSession
  ): Promise<void> {
    // Send progress
    server.send(JSON.stringify({
      type: 'agent_progress',
      agentType: 'build',
      progress: 10,
      message: 'Starting code generation...'
    }));

    // Approve plan and start build
    const result = await session.mainAgent.approvePlan();

    if (result.success) {
      // Send file updates
      if (result.files) {
        for (const file of result.files) {
          server.send(JSON.stringify({
            type: 'file_generated',
            file: {
              path: file.path,
              content: file.content,
              action: file.action
            }
          }));
        }
      }

      server.send(JSON.stringify({
        type: 'assistant_message',
        content: `Project generated successfully! ${result.files?.length || 0} files created.`
      }));
    } else {
      server.send(JSON.stringify({
        type: 'error',
        error: result.error || 'Build failed'
      }));
    }

    // Send completion
    server.send(JSON.stringify({
      type: 'agent_progress',
      agentType: 'build',
      progress: 100,
      message: 'Build complete!'
    }));

    server.send(JSON.stringify({
      type: 'generation_complete'
    }));
  }

  /**
   * Handle file operation confirmation
   */
  private static async handleFileOperationConfirm(
    server: WebSocket,
    session: AgentSession,
    data: any
  ): Promise<void> {
    const { confirmed } = data;

    if (confirmed) {
      // Execute file operation
      server.send(JSON.stringify({
        type: 'agent_progress',
        agentType: 'build',
        progress: 50,
        message: 'Executing file operation...'
      }));

      // Here you would execute the actual file operation
      // For now, just send success
      server.send(JSON.stringify({
        type: 'file_operation_complete',
        operation: 'delete',
        filePath: 'example/path',
        success: true,
        message: 'File operation completed'
      }));
    } else {
      server.send(JSON.stringify({
        type: 'file_operation_complete',
        operation: 'delete',
        filePath: 'example/path',
        success: false,
        message: 'File operation cancelled'
      }));
    }
  }

  /**
   * Handle deployment
   */
  private static async handleDeploy(
    server: WebSocket,
    session: AgentSession,
    data: any,
    env: Env
  ): Promise<void> {
    const { action } = data;

    if (action === 'connect') {
      // Check if CF account is connected
      server.send(JSON.stringify({
        type: 'deployment_status',
        status: 'connecting',
        message: 'Checking Cloudflare account...'
      }));

      // Here you would check CF account status
      // For now, simulate
      setTimeout(() => {
        server.send(JSON.stringify({
          type: 'deployment_status',
          status: 'error',
          message: 'Cloudflare account not connected',
          error: 'Please connect your Cloudflare account first'
        }));
      }, 1000);

    } else if (action === 'deploy') {
      server.send(JSON.stringify({
        type: 'deployment_status',
        status: 'deploying',
        message: 'Deploying to Cloudflare...'
      }));

      // Here you would deploy to CF
      // For now, simulate
      setTimeout(() => {
        server.send(JSON.stringify({
          type: 'deployment_status',
          status: 'deployed',
          message: 'Deployment successful!',
          previewUrl: 'https://preview.example.workers.dev'
        }));
      }, 2000);
    }
  }

  /**
   * Get session status
   */
  static async getSessionStatus(
    request: Request,
    env: Env,
    _: ExecutionContext,
    context: RouteContext
  ): Promise<Response> {
    try {
      const sessionId = context.pathParams.sessionId;
      const session = this.sessions.get(sessionId);

      if (!session) {
        return this.createErrorResponse('Session not found', 404);
      }

      return new Response(JSON.stringify({
        success: true,
        session: {
          id: session.id,
          status: session.status,
          currentPlan: session.currentPlan,
          planStatus: session.planStatus,
          createdAt: session.createdAt
        }
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      this.logger.error('Error getting session status', error);
      return this.createErrorResponse(error, 500);
    }
  }
}
