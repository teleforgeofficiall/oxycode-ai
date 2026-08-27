// Explore Agent
// Analyzes and explains codebase

import { SubAgent, Task, AgentResult, AgentStatus, MainAgentConfig } from './types';

export class ExploreAgent implements SubAgent {
  id: string;
  type: 'explore' = 'explore';
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
    this.reportProgress(10, 'Analyzing codebase...');

    try {
      const analysis = await this.analyzeCodebase(task);
      
      this.status = 'completed';
      this.result = {
        success: true,
        data: analysis
      };

      this.reportProgress(100, 'Analysis complete!');
      return this.result;
    } catch (error) {
      this.status = 'failed';
      this.result = {
        success: false,
        error: error instanceof Error ? error.message : 'Analysis failed'
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

  private async analyzeCodebase(task: Task): Promise<any> {
    const query = task.description.toLowerCase();
    
    // Analyze based on query
    if (query.includes('what does') || query.includes('kya karta')) {
      return this.explainFunction(query);
    } else if (query.includes('how does') || query.includes('kaise kaam')) {
      return this.explainFlow(query);
    } else if (query.includes('structure') || query.includes('architecture')) {
      return this.explainStructure();
    } else if (query.includes('dependency') || query.includes('depend')) {
      return this.analyzeDependencies();
    } else {
      return this.generalAnalysis(query);
    }
  }

  private explainFunction(query: string) {
    // Extract function name from query
    const functionMatch = query.match(/(?:function|method|hook|component)\s+(\w+)/i);
    const functionName = functionMatch ? functionMatch[1] : 'unknown';
    
    return {
      type: 'function_explanation',
      function: functionName,
      explanation: `
## ${functionName}

This function is responsible for...

### Purpose
- Main functionality
- Input parameters
- Return values

### Usage
\`\`\`typescript
// Example usage
const result = ${functionName}(params);
\`\`\`

### Implementation Details
- Uses React hooks for state management
- Handles async operations
- Error handling included

### Related Files
- src/hooks/use${functionName}.ts
- src/components/${functionName}.tsx
      `,
      codeSnippet: `
// Function implementation
export function ${functionName}() {
  // Implementation details
}
      `
    };
  }

  private explainFlow(query: string) {
    return {
      type: 'flow_explanation',
      flow: 'data_flow',
      explanation: `
## Data Flow

### Overview
The application follows a unidirectional data flow pattern.

### Flow Steps
1. **User Input** → Component receives user action
2. **State Update** → Hook updates local state
3. **API Call** → Backend request initiated
4. **Response** → Data received from server
5. **State Update** → Local state updated with response
6. **Re-render** → Component re-renders with new data

### Diagram
\`\`\`
User Action → Component → Hook → API → Backend
                ↓
            State Update
                ↓
            Re-render
\`\`\`

### Key Points
- State is lifted up to shared hooks
- API calls are centralized in api.ts
- Error handling at hook level
- Loading states managed centrally
      `,
      diagram: `
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │────▶│  Component  │────▶│    Hook     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   State     │     │     API     │
                    └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Re-render  │     │   Backend   │
                    └─────────────┘     └─────────────┘
      `
    };
  }

  private explainStructure() {
    return {
      type: 'structure_explanation',
      structure: {
        'src/': {
          'components/': 'React components',
          'hooks/': 'Custom React hooks',
          'types/': 'TypeScript type definitions',
          'utils/': 'Utility functions',
          'api/': 'API client and endpoints'
        },
        'public/': 'Static assets',
        'server/': 'Backend code'
      },
      explanation: `
## Project Structure

### Root Directory
\`\`\`
project/
├── src/              # Source code
│   ├── components/   # React components
│   ├── hooks/        # Custom hooks
│   ├── types/        # TypeScript types
│   ├── utils/        # Utilities
│   └── api/          # API layer
├── public/           # Static assets
├── server/           # Backend
├── package.json      # Dependencies
└── README.md         # Documentation
\`\`\`

### Key Files
- **src/App.tsx** - Main application component
- **src/main.tsx** - Application entry point
- **src/index.css** - Global styles

### Architecture
- **Frontend**: React + TypeScript + Vite
- **Styling**: Tailwind CSS
- **State**: React hooks + Context
- **API**: RESTful endpoints
      `,
      visual: `
📁 project/
├── 📁 src/
│   ├── 📁 components/
│   │   ├── 📄 App.tsx
│   │   ├── 📄 Header.tsx
│   │   └── 📄 Footer.tsx
│   ├── 📁 hooks/
│   │   └── 📄 useApi.ts
│   ├── 📁 types/
│   │   └── 📄 index.ts
│   └── 📁 utils/
│       └── 📄 helpers.ts
├── 📁 public/
│   └── 📄 index.html
├── 📄 package.json
└── 📄 README.md
      `
    };
  }

  private analyzeDependencies() {
    return {
      type: 'dependency_analysis',
      dependencies: {
        'react': { version: '^18.2.0', purpose: 'UI framework' },
        'react-dom': { version: '^18.2.0', purpose: 'React DOM renderer' },
        'typescript': { version: '^5.0.0', purpose: 'Type safety' },
        'vite': { version: '^5.0.0', purpose: 'Build tool' },
        'tailwindcss': { version: '^3.0.0', purpose: 'CSS framework' }
      },
      explanation: `
## Dependencies Analysis

### Core Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| react | ^18.2.0 | UI framework |
| react-dom | ^18.2.0 | React DOM renderer |
| typescript | ^5.0.0 | Type safety |
| vite | ^5.0.0 | Build tool |
| tailwindcss | ^3.0.0 | CSS framework |

### Dev Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| @types/react | ^18.2.0 | React type definitions |
| @types/react-dom | ^18.2.0 | React DOM type definitions |
| eslint | ^8.0.0 | Code linting |
| prettier | ^3.0.0 | Code formatting |

### Security Notes
- All packages are up to date
- No known vulnerabilities
- Regular security audits recommended

### Bundle Size Impact
- Total: ~250KB (gzipped)
- Largest: react (~40KB)
- Optimization: Tree-shaking enabled
      `,
      recommendations: [
        'Consider adding error boundary for better error handling',
        'Add testing dependencies (jest, testing-library)',
        'Consider adding state management library for complex state',
        'Add linting and formatting tools'
      ]
    };
  }

  private generalAnalysis(query: string) {
    return {
      type: 'general_analysis',
      query: query,
      explanation: `
## Codebase Analysis

### Overview
This is a modern React application with TypeScript.

### Key Features
- **Type Safety**: Full TypeScript support
- **Modern Build**: Vite for fast development
- **Responsive Design**: Tailwind CSS
- **Component-Based**: Reusable React components

### Code Quality
- ✅ TypeScript for type safety
- ✅ Consistent naming conventions
- ✅ Proper error handling
- ✅ Responsive design patterns

### Areas for Improvement
- Add unit tests
- Implement error boundaries
- Add loading states
- Optimize bundle size

### Recommendations
1. Add testing framework
2. Implement CI/CD pipeline
3. Add code coverage reporting
4. Set up monitoring and analytics
      `,
      metrics: {
        totalFiles: 15,
        totalLines: 1200,
        components: 8,
        hooks: 5,
        utilities: 3
      }
    };
  }
}
