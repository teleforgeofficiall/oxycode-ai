// Debug Agent
// Finds and fixes bugs in code

import { SubAgent, Task, AgentResult, AgentStatus, FileInfo, MainAgentConfig } from './types';

export class DebugAgent implements SubAgent {
  id: string;
  type: 'debug' = 'debug';
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
    this.reportProgress(10, 'Analyzing error...');

    try {
      const analysis = await this.analyzeAndFix(task);
      
      this.status = 'completed';
      this.result = {
        success: true,
        data: analysis,
        files: analysis.fixes || []
      };

      this.reportProgress(100, 'Bug fixed!');
      return this.result;
    } catch (error) {
      this.status = 'failed';
      this.result = {
        success: false,
        error: error instanceof Error ? error.message : 'Debug failed'
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

  private async analyzeAndFix(task: Task): Promise<any> {
    const errorDescription = task.description;
    
    // Analyze error type
    const errorType = this.detectErrorType(errorDescription);
    
    // Find root cause
    const rootCause = this.findRootCause(errorDescription, errorType);
    
    // Generate fix
    const fix = this.generateFix(errorType, rootCause);
    
    // Generate explanation
    const explanation = this.generateExplanation(errorType, rootCause, fix);

    return {
      errorType,
      rootCause,
      fix,
      explanation,
      fixes: fix.files || []
    };
  }

  private detectErrorType(errorDescription: string): string {
    const lowerError = errorDescription.toLowerCase();
    
    // TypeScript errors
    if (lowerError.includes('type') && lowerError.includes('error')) {
      return 'typescript_type_error';
    }
    if (lowerError.includes('cannot find') && lowerError.includes('module')) {
      return 'module_not_found';
    }
    if (lowerError.includes('property') && lowerError.includes('does not exist')) {
      return 'property_not_exist';
    }
    
    // React errors
    if (lowerError.includes('render') && lowerError.includes('error')) {
      return 'react_render_error';
    }
    if (lowerError.includes('hook')) {
      return 'react_hook_error';
    }
    if (lowerError.includes('cannot update') && lowerError.includes('state')) {
      return 'state_update_error';
    }
    
    // Network errors
    if (lowerError.includes('fetch') || lowerError.includes('network')) {
      return 'network_error';
    }
    if (lowerError.includes('cors')) {
      return 'cors_error';
    }
    
    // Build errors
    if (lowerError.includes('build') || lowerError.includes('compile')) {
      return 'build_error';
    }
    
    // Runtime errors
    if (lowerError.includes('undefined') || lowerError.includes('null')) {
      return 'null_reference_error';
    }
    if (lowerError.includes('is not a function')) {
      return 'not_a_function_error';
    }
    
    return 'unknown_error';
  }

  private findRootCause(errorDescription: string, errorType: string): string {
    switch (errorType) {
      case 'typescript_type_error':
        return 'Type mismatch in function parameters or return type';
      case 'module_not_found':
        return 'Missing import or incorrect path';
      case 'property_not_exist':
        return 'Accessing non-existent property on object';
      case 'react_render_error':
        return 'Error in component render method';
      case 'react_hook_error':
        return 'Hook called outside component or in wrong order';
      case 'state_update_error':
        return 'State update on unmounted component';
      case 'network_error':
        return 'API endpoint unreachable or timeout';
      case 'cors_error':
        return 'Cross-origin request blocked';
      case 'build_error':
        return 'Compilation or bundling issue';
      case 'null_reference_error':
        return 'Accessing property of null/undefined';
      case 'not_a_function_error':
        return 'Calling non-function as function';
      default:
        return 'Unknown root cause';
    }
  }

  private generateFix(errorType: string, rootCause: string): any {
    const fixes: FileInfo[] = [];
    let solution = '';
    
    switch (errorType) {
      case 'typescript_type_error':
        solution = 'Fix type annotations to match expected types';
        fixes.push({
          path: 'src/types/index.ts',
          content: `// Fixed type definitions
export interface FixedType {
  // Add proper type definitions here
}
`,
          action: 'update'
        });
        break;
        
      case 'module_not_found':
        solution = 'Check import path and ensure module exists';
        fixes.push({
          path: 'src/App.tsx',
          content: `// Fixed import path
import { CorrectPath } from './correct/path';
`,
          action: 'update'
        });
        break;
        
      case 'property_not_exist':
        solution = 'Add optional chaining or check property existence';
        fixes.push({
          path: 'src/components/FixedComponent.tsx',
          content: `// Fixed with optional chaining
const value = object?.property ?? defaultValue;
`,
          action: 'update'
        });
        break;
        
      case 'react_render_error':
        solution = 'Fix component render logic';
        fixes.push({
          path: 'src/components/FixedComponent.tsx',
          content: `// Fixed render logic
import React from 'react';

export default function FixedComponent() {
  return (
    <div>
      {/* Fixed content */}
    </div>
  );
}
`,
          action: 'update'
        });
        break;
        
      case 'react_hook_error':
        solution = 'Ensure hooks are called in correct order';
        fixes.push({
          path: 'src/hooks/useFixedHook.ts',
          content: `// Fixed hook usage
import { useState, useEffect } from 'react';

export function useFixedHook() {
  const [state, setState] = useState(null);
  
  useEffect(() => {
    // Proper cleanup
    return () => {};
  }, []);
  
  return state;
}
`,
          action: 'update'
        });
        break;
        
      case 'state_update_error':
        solution = 'Add cleanup flag for async operations';
        fixes.push({
          path: 'src/hooks/useAsyncOperation.ts',
          content: `// Fixed with cleanup
import { useState, useEffect } from 'react';

export function useAsyncOperation() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    let cancelled = false;
    
    const fetchData = async () => {
      setLoading(true);
      try {
        const result = await someAsyncOperation();
        if (!cancelled) {
          setData(result);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    
    fetchData();
    
    return () => {
      cancelled = true;
    };
  }, []);
  
  return { data, loading };
}
`,
          action: 'update'
        });
        break;
        
      case 'network_error':
        solution = 'Add error handling and retry logic';
        fixes.push({
          path: 'src/utils/api.ts',
          content: `// Fixed with error handling and retry
export async function fetchWithRetry(url: string, options?: RequestInit, retries = 3): Promise<Response> {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(\`HTTP error! status: \${response.status}\`);
      }
      return response;
    } catch (error) {
      if (i === retries - 1) throw error;
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
    }
  }
  throw new Error('Max retries exceeded');
}
`,
          action: 'update'
        });
        break;
        
      case 'cors_error':
        solution = 'Configure CORS headers or use proxy';
        fixes.push({
          path: 'vite.config.ts',
          content: `// Fixed CORS with proxy
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        secure: false
      }
    }
  }
});
`,
          action: 'update'
        });
        break;
        
      case 'null_reference_error':
        solution = 'Add null checks and default values';
        fixes.push({
          path: 'src/components/SafeComponent.tsx',
          content: `// Fixed with null checks
import React from 'react';

interface Props {
  data?: {
    name?: string;
    value?: number;
  };
}

export default function SafeComponent({ data }: Props) {
  const name = data?.name ?? 'Unknown';
  const value = data?.value ?? 0;
  
  return (
    <div>
      <p>Name: {name}</p>
      <p>Value: {value}</p>
    </div>
  );
}
`,
          action: 'update'
        });
        break;
        
      case 'not_a_function_error':
        solution = 'Check if value is a function before calling';
        fixes.push({
          path: 'src/utils/safeFunctionCall.ts',
          content: `// Fixed with type checking
export function safeFunctionCall(fn: unknown, ...args: any[]): any {
  if (typeof fn === 'function') {
    return fn(...args);
  }
  console.warn('Expected function but got:', typeof fn);
  return undefined;
}
`,
          action: 'update'
        });
        break;
        
      default:
        solution = 'Review code and fix the issue';
    }
    
    return {
      solution,
      files: fixes,
      steps: [
        'Identify the exact line causing the error',
        'Apply the fix',
        'Test the fix',
        'Verify no regressions'
      ]
    };
  }

  private generateExplanation(errorType: string, rootCause: string, fix: any): string {
    return `
## Bug Analysis

### Error Type
${errorType.replace(/_/g, ' ').toUpperCase()}

### Root Cause
${rootCause}

### Solution
${fix.solution}

### Steps to Fix
${fix.steps.map((step: string, i: number) => `${i + 1}. ${step}`).join('\n')}

### Files to Modify
${fix.files.map((f: FileInfo) => `- ${f.path}`).join('\n')}

### Prevention Tips
- Add TypeScript strict mode
- Use proper error handling
- Add unit tests for edge cases
- Use linting rules
    `;
  }
}
