// Planner Agent
// Generates project plans with file structure

import { SubAgent, Task, AgentResult, AgentStatus, PlanData, PlanFile, MainAgentConfig } from './types';

export class PlannerAgent implements SubAgent {
  id: string;
  type: 'planner' = 'planner';
  status: AgentStatus = 'idle';
  private config: MainAgentConfig;
  private result: AgentResult | null = null;
  private onProgress?: (progress: number, message: string) => void;

  constructor(id: string, config: MainAgentConfig) {
    this.id = id;
    this.config = config;
  }

  async execute(task: Task): Promise<AgentResult> {
    this.status = 'working';
    this.reportProgress(10, 'Analyzing task...');

    try {
      // Analyze task and generate plan
      const plan = await this.generatePlan(task);
      
      this.status = 'completed';
      this.result = {
        success: true,
        data: plan,
        plan: plan
      };

      this.reportProgress(100, 'Plan generated!');
      return this.result;
    } catch (error) {
      this.status = 'failed';
      this.result = {
        success: false,
        error: error instanceof Error ? error.message : 'Plan generation failed'
      };
      return this.result;
    }
  }

  reportProgress(progress: number, message: string) {
    if (this.onProgress) {
      this.onProgress(progress, message);
    }
  }

  getResult(): AgentResult {
    return this.result || { success: false, error: 'No result yet' };
  }

  setOnProgress(callback: (progress: number, message: string) => void) {
    this.onProgress = callback;
  }

  private async generatePlan(task: Task): Promise<PlanData> {
    const description = task.description;
    
    // Analyze the task to determine project type and requirements
    const analysis = this.analyzeTask(description);
    
    // Generate file structure based on analysis
    const files = this.generateFileStructure(analysis);
    
    // Generate folder structure display
    const folderStructure = this.generateFolderDisplay(files);
    
    // Calculate estimated time
    const estimatedTime = this.estimateTime(files);

    return {
      overview: analysis.overview,
      files: files,
      folderStructure: folderStructure,
      estimatedTime: estimatedTime
    };
  }

  private analyzeTask(description: string) {
    const lowerDesc = description.toLowerCase();
    
    // Detect project features
    const features: string[] = [];
    const techStack: string[] = ['React', 'TypeScript'];
    
    if (lowerDesc.includes('payment') || lowerDesc.includes('stripe')) {
      features.push('Payment Integration');
      techStack.push('Stripe');
    }
    if (lowerDesc.includes('auth') || lowerDesc.includes('login')) {
      features.push('Authentication');
    }
    if (lowerDesc.includes('database') || lowerDesc.includes('db')) {
      features.push('Database');
      techStack.push('PostgreSQL');
    }
    if (lowerDesc.includes('api') || lowerDesc.includes('backend')) {
      features.push('API');
      techStack.push('Node.js');
    }
    if (lowerDesc.includes('todo') || lowerDesc.includes('task')) {
      features.push('Task Management');
    }
    if (lowerDesc.includes('chat') || lowerDesc.includes('message')) {
      features.push('Real-time Chat');
      techStack.push('WebSocket');
    }
    if (lowerDesc.includes('ecommerce') || lowerDesc.includes('shop')) {
      features.push('E-commerce');
    }
    if (lowerDesc.includes('blog') || lowerDesc.includes('cms')) {
      features.push('CMS');
    }
    if (lowerDesc.includes('dashboard') || lowerDesc.includes('admin')) {
      features.push('Dashboard');
    }
    if (lowerDesc.includes('dark mode') || lowerDesc.includes('theme')) {
      features.push('Dark Mode');
    }

    // Generate overview
    const overview = this.generateOverview(description, features, techStack);

    return {
      overview,
      features,
      techStack
    };
  }

  private generateOverview(description: string, features: string[], techStack: string[]): string {
    let overview = `Project: ${description}\n\n`;
    
    if (features.length > 0) {
      overview += `Features:\n`;
      features.forEach(f => overview += `- ${f}\n`);
    }
    
    overview += `\nTech Stack: ${techStack.join(', ')}`;
    
    return overview;
  }

  private generateFileStructure(analysis: { overview: string; features: string[]; techStack: string[] }): PlanFile[] {
    const files: PlanFile[] = [];
    
    // Base files
    files.push({
      path: 'package.json',
      purpose: 'Project dependencies and scripts',
      complexity: 'low'
    });
    files.push({
      path: 'README.md',
      purpose: 'Project documentation',
      complexity: 'low'
    });
    files.push({
      path: 'tsconfig.json',
      purpose: 'TypeScript configuration',
      complexity: 'low'
    });

    // Component files
    files.push({
      path: 'src/App.tsx',
      purpose: 'Main application component',
      complexity: 'medium'
    });
    files.push({
      path: 'src/main.tsx',
      purpose: 'Application entry point',
      complexity: 'low'
    });
    files.push({
      path: 'src/index.css',
      purpose: 'Global styles',
      complexity: 'low'
    });

    // Feature-specific files
    if (analysis.features.includes('Task Management')) {
      files.push({
        path: 'src/components/TodoList.tsx',
        purpose: 'Todo list component',
        complexity: 'medium'
      });
      files.push({
        path: 'src/components/TodoItem.tsx',
        purpose: 'Individual todo item component',
        complexity: 'low'
      });
      files.push({
        path: 'src/components/AddTodo.tsx',
        purpose: 'Add new todo component',
        complexity: 'low'
      });
      files.push({
        path: 'src/hooks/useTodos.ts',
        purpose: 'Todo state management hook',
        complexity: 'medium'
      });
      files.push({
        path: 'src/types/todo.ts',
        purpose: 'Todo type definitions',
        complexity: 'low'
      });
    }

    if (analysis.features.includes('Payment Integration')) {
      files.push({
        path: 'src/payment/stripe.ts',
        purpose: 'Stripe configuration and helpers',
        complexity: 'medium'
      });
      files.push({
        path: 'src/payment/webhook.ts',
        purpose: 'Payment webhook handler',
        complexity: 'high'
      });
      files.push({
        path: 'src/payment/types.ts',
        purpose: 'Payment type definitions',
        complexity: 'low'
      });
      files.push({
        path: 'src/components/PaymentForm.tsx',
        purpose: 'Payment form component',
        complexity: 'medium'
      });
    }

    if (analysis.features.includes('Authentication')) {
      files.push({
        path: 'src/auth/AuthContext.tsx',
        purpose: 'Authentication context provider',
        complexity: 'medium'
      });
      files.push({
        path: 'src/auth/Login.tsx',
        purpose: 'Login page',
        complexity: 'medium'
      });
      files.push({
        path: 'src/auth/Register.tsx',
        purpose: 'Registration page',
        complexity: 'medium'
      });
      files.push({
        path: 'src/auth/useAuth.ts',
        purpose: 'Authentication hook',
        complexity: 'medium'
      });
    }

    if (analysis.features.includes('Real-time Chat')) {
      files.push({
        path: 'src/components/Chat.tsx',
        purpose: 'Chat component',
        complexity: 'high'
      });
      files.push({
        path: 'src/components/Message.tsx',
        purpose: 'Message component',
        complexity: 'medium'
      });
      files.push({
        path: 'src/hooks/useWebSocket.ts',
        purpose: 'WebSocket connection hook',
        complexity: 'high'
      });
    }

    if (analysis.features.includes('E-commerce')) {
      files.push({
        path: 'src/components/ProductList.tsx',
        purpose: 'Product listing component',
        complexity: 'medium'
      });
      files.push({
        path: 'src/components/ProductCard.tsx',
        purpose: 'Product card component',
        complexity: 'low'
      });
      files.push({
        path: 'src/components/Cart.tsx',
        purpose: 'Shopping cart component',
        complexity: 'medium'
      });
      files.push({
        path: 'src/hooks/useCart.ts',
        purpose: 'Cart state management hook',
        complexity: 'medium'
      });
    }

    if (analysis.features.includes('Dashboard')) {
      files.push({
        path: 'src/components/Dashboard.tsx',
        purpose: 'Dashboard layout',
        complexity: 'medium'
      });
      files.push({
        path: 'src/components/StatsCard.tsx',
        purpose: 'Statistics card component',
        complexity: 'low'
      });
      files.push({
        path: 'src/components/Chart.tsx',
        purpose: 'Chart component',
        complexity: 'medium'
      });
    }

    // Utility files
    files.push({
      path: 'src/utils/api.ts',
      purpose: 'API client utilities',
      complexity: 'medium'
    });
    files.push({
      path: 'src/utils/helpers.ts',
      purpose: 'Helper functions',
      complexity: 'low'
    });

    return files;
  }

  private generateFolderDisplay(files: PlanFile[]): string {
    const tree: string[] = ['📁 project/'];
    
    // Group files by directory
    const directories = new Map<string, PlanFile[]>();
    
    files.forEach(file => {
      const parts = file.path.split('/');
      if (parts.length > 1) {
        const dir = parts.slice(0, -1).join('/');
        if (!directories.has(dir)) {
          directories.set(dir, []);
        }
        directories.get(dir)!.push(file);
      } else {
        if (!directories.has('')) {
          directories.set('', []);
        }
        directories.get('')!.push(file);
      }
    });

    // Build tree string
    directories.forEach((dirFiles, dir) => {
      if (dir) {
        tree.push(`├── 📁 ${dir}/`);
        dirFiles.forEach((file, index) => {
          const prefix = index === dirFiles.length - 1 ? '└── ' : '├── ';
          const fileName = file.path.split('/').pop() || '';
          tree.push(`│   ${prefix}📄 ${fileName}`);
        });
      } else {
        dirFiles.forEach(file => {
          tree.push(`├── 📄 ${file.path}`);
        });
      }
    });

    return tree.join('\n');
  }

  private estimateTime(files: PlanFile[]): string {
    const totalFiles = files.length;
    const highComplexity = files.filter(f => f.complexity === 'high').length;
    const mediumComplexity = files.filter(f => f.complexity === 'medium').length;
    
    // Estimate minutes
    const minutes = (highComplexity * 3) + (mediumComplexity * 2) + ((totalFiles - highComplexity - mediumComplexity) * 1);
    
    if (minutes < 5) return '2-5 minutes';
    if (minutes < 10) return '5-10 minutes';
    if (minutes < 20) return '10-20 minutes';
    return '20-30 minutes';
  }
}
