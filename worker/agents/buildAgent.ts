// Build Agent
// Generates code files and manages file operations

import { SubAgent, Task, AgentResult, AgentStatus, FileInfo, MainAgentConfig } from './types';

export class BuildAgent implements SubAgent {
  id: string;
  type: 'build' = 'build';
  status: AgentStatus = 'idle';
  private config: MainAgentConfig;
  private result: AgentResult | null = null;
  private onProgress?: (progress: number, message: string) => void;
  private onFileUpdate?: (files: FileInfo[]) => void;

  constructor(id: string, config: MainAgentConfig) {
    this.id = id;
    this.config = config;
  }

  async execute(task: Task): Promise<AgentResult> {
    this.status = 'working';
    this.reportProgress(10, 'Preparing to generate code...');

    try {
      let result: AgentResult;

      switch (task.type) {
        case 'create_project':
          result = await this.generateProject(task);
          break;
        case 'file_operation':
          result = await this.handleFileOperation(task);
          break;
        default:
          result = await this.generateProject(task);
      }

      this.status = 'completed';
      this.result = result;
      this.reportProgress(100, 'Build completed!');
      return result;
    } catch (error) {
      this.status = 'failed';
      this.result = {
        success: false,
        error: error instanceof Error ? error.message : 'Build failed'
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

  setOnFileUpdate(callback: (files: FileInfo[]) => void) {
    this.onFileUpdate = callback;
  }

  private async generateProject(task: Task): Promise<AgentResult> {
    const files: FileInfo[] = [];
    
    // Generate files based on task description
    const generatedFiles = await this.generateFilesFromTask(task);
    files.push(...generatedFiles);

    // Report file updates
    if (this.onFileUpdate) {
      this.onFileUpdate(files);
    }

    return {
      success: true,
      data: {
        message: 'Project generated successfully',
        fileCount: files.length
      },
      files: files
    };
  }

  private async generateFilesFromTask(task: Task): Promise<FileInfo[]> {
    const files: FileInfo[] = [];
    const description = task.description.toLowerCase();

    // Generate package.json
    files.push({
      path: 'package.json',
      content: this.generatePackageJson(description),
      action: 'create'
    });

    // Generate README.md
    files.push({
      path: 'README.md',
      content: this.generateReadme(description),
      action: 'create'
    });

    // Generate tsconfig.json
    files.push({
      path: 'tsconfig.json',
      content: this.generateTsConfig(),
      action: 'create'
    });

    // Generate main files
    files.push({
      path: 'src/main.tsx',
      content: this.generateMainTsx(),
      action: 'create'
    });

    files.push({
      path: 'src/index.css',
      content: this.generateIndexCss(),
      action: 'create'
    });

    // Generate App.tsx
    files.push({
      path: 'src/App.tsx',
      content: this.generateAppTsx(description),
      action: 'create'
    });

    // Generate feature-specific files
    if (description.includes('todo') || description.includes('task')) {
      files.push(...this.generateTodoFiles());
    }

    if (description.includes('payment') || description.includes('stripe')) {
      files.push(...this.generatePaymentFiles());
    }

    if (description.includes('auth') || description.includes('login')) {
      files.push(...this.generateAuthFiles());
    }

    if (description.includes('chat') || description.includes('message')) {
      files.push(...this.generateChatFiles());
    }

    if (description.includes('ecommerce') || description.includes('shop')) {
      files.push(...this.generateEcommerceFiles());
    }

    if (description.includes('dashboard') || description.includes('admin')) {
      files.push(...this.generateDashboardFiles());
    }

    return files;
  }

  private generatePackageJson(description: string): string {
    const dependencies: Record<string, string> = {
      'react': '^18.2.0',
      'react-dom': '^18.2.0',
      'typescript': '^5.0.0',
      '@types/react': '^18.2.0',
      '@types/react-dom': '^18.2.0',
      'vite': '^5.0.0',
      '@vitejs/plugin-react': '^4.0.0'
    };

    if (description.includes('payment') || description.includes('stripe')) {
      dependencies['@stripe/stripe-js'] = '^2.0.0';
      dependencies['@stripe/react-stripe-js'] = '^2.0.0';
    }

    if (description.includes('router') || description.includes('navigation')) {
      dependencies['react-router-dom'] = '^6.0.0';
    }

    if (description.includes('state') || description.includes('global')) {
      dependencies['zustand'] = '^4.0.0';
    }

    return JSON.stringify({
      name: 'todo-app',
      version: '1.0.0',
      type: 'module',
      scripts: {
        dev: 'vite',
        build: 'tsc && vite build',
        preview: 'vite preview'
      },
      dependencies,
      devDependencies: {
        '@types/node': '^20.0.0'
      }
    }, null, 2);
  }

  private generateReadme(description: string): string {
    return `# Todo App

${description}

## Features

- Modern React with TypeScript
- Vite for fast development
- Responsive design

## Getting Started

\`\`\`bash
npm install
npm run dev
\`\`\`

## Build

\`\`\`bash
npm run build
\`\`\`

## Technologies

- React 18
- TypeScript
- Vite
- Tailwind CSS
`;
  }

  private generateTsConfig(): string {
    return JSON.stringify({
      compilerOptions: {
        target: 'ES2020',
        useDefineForClassFields: true,
        lib: ['ES2020', 'DOM', 'DOM.Iterable'],
        module: 'ESNext',
        skipLibCheck: true,
        moduleResolution: 'bundler',
        allowImportingTsExtensions: true,
        resolveJsonModule: true,
        isolatedModules: true,
        noEmit: true,
        jsx: 'react-jsx',
        strict: true,
        noUnusedLocals: true,
        noUnusedParameters: true,
        noFallthroughCasesInSwitch: true
      },
      include: ['src'],
      references: [{ path: './tsconfig.node.json' }]
    }, null, 2);
  }

  private generateMainTsx(): string {
    return `import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
`;
  }

  private generateIndexCss(): string {
    return `@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}
`;
  }

  private generateAppTsx(description: string): string {
    return `import React from 'react'

function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Todo App
        </h1>
        {/* Components will be added here */}
      </div>
    </div>
  )
}

export default App
`;
  }

  private generateTodoFiles(): FileInfo[] {
    return [
      {
        path: 'src/types/todo.ts',
        content: `export interface Todo {
  id: string;
  title: string;
  completed: boolean;
  createdAt: Date;
}

export type CreateTodoInput = Omit<Todo, 'id' | 'createdAt'>;
`,
        action: 'create'
      },
      {
        path: 'src/hooks/useTodos.ts',
        content: `import { useState, useCallback } from 'react';
import { Todo, CreateTodoInput } from '../types/todo';

export function useTodos() {
  const [todos, setTodos] = useState<Todo[]>([]);

  const addTodo = useCallback((input: CreateTodoInput) => {
    const newTodo: Todo = {
      ...input,
      id: crypto.randomUUID(),
      createdAt: new Date()
    };
    setTodos(prev => [...prev, newTodo]);
  }, []);

  const toggleTodo = useCallback((id: string) => {
    setTodos(prev =>
      prev.map(todo =>
        todo.id === id ? { ...todo, completed: !todo.completed } : todo
      )
    );
  }, []);

  const deleteTodo = useCallback((id: string) => {
    setTodos(prev => prev.filter(todo => todo.id !== id));
  }, []);

  return { todos, addTodo, toggleTodo, deleteTodo };
}
`,
        action: 'create'
      },
      {
        path: 'src/components/TodoList.tsx',
        content: `import React from 'react';
import { Todo } from '../types/todo';
import TodoItem from './TodoItem';

interface TodoListProps {
  todos: Todo[];
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function TodoList({ todos, onToggle, onDelete }: TodoListProps) {
  if (todos.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No todos yet. Add one above!
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {todos.map(todo => (
        <TodoItem
          key={todo.id}
          todo={todo}
          onToggle={onToggle}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/TodoItem.tsx',
        content: `import React from 'react';
import { Todo } from '../types/todo';

interface TodoItemProps {
  todo: Todo;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function TodoItem({ todo, onToggle, onDelete }: TodoItemProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-white rounded-lg shadow">
      <div className="flex items-center space-x-3">
        <input
          type="checkbox"
          checked={todo.completed}
          onChange={() => onToggle(todo.id)}
          className="w-5 h-5 text-blue-600 rounded"
        />
        <span className={\`text-gray-900 \${todo.completed ? 'line-through text-gray-500' : ''}\`}>
          {todo.title}
        </span>
      </div>
      <button
        onClick={() => onDelete(todo.id)}
        className="text-red-500 hover:text-red-700"
      >
        Delete
      </button>
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/AddTodo.tsx',
        content: `import React, { useState } from 'react';

interface AddTodoProps {
  onAdd: (title: string) => void;
}

export default function AddTodo({ onAdd }: AddTodoProps) {
  const [title, setTitle] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title.trim()) {
      onAdd(title.trim());
      setTitle('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex space-x-2">
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Add a new todo..."
        className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <button
        type="submit"
        className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
      >
        Add
      </button>
    </form>
  );
}
`,
        action: 'create'
      }
    ];
  }

  private generatePaymentFiles(): FileInfo[] {
    return [
      {
        path: 'src/payment/types.ts',
        content: `export interface PaymentIntent {
  id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'succeeded' | 'failed';
}

export interface CheckoutSession {
  id: string;
  paymentIntentId: string;
  customerEmail: string;
}
`,
        action: 'create'
      },
      {
        path: 'src/payment/stripe.ts',
        content: `import { loadStripe } from '@stripe/stripe-js';

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY);

export { stripePromise };
`,
        action: 'create'
      },
      {
        path: 'src/components/PaymentForm.tsx',
        content: `import React from 'react';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { stripePromise } from '../payment/stripe';

function PaymentFormInner() {
  const stripe = useStripe();
  const elements = useElements();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    // Payment processing logic here
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <CardElement className="p-4 border rounded" />
      <button
        type="submit"
        disabled={!stripe}
        className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
      >
        Pay Now
      </button>
    </form>
  );
}

export default function PaymentForm() {
  return (
    <Elements stripe={stripePromise}>
      <PaymentFormInner />
    </Elements>
  );
}
`,
        action: 'create'
      }
    ];
  }

  private generateAuthFiles(): FileInfo[] {
    return [
      {
        path: 'src/auth/types.ts',
        content: `export interface User {
  id: string;
  email: string;
  name: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
`,
        action: 'create'
      },
      {
        path: 'src/auth/useAuth.ts',
        content: `import { useState, useCallback } from 'react';
import { User, AuthState } from './types';

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: false
  });

  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true }));
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    setState({
      user: { id: '1', email, name: 'User' },
      isAuthenticated: true,
      isLoading: false
    });
  }, []);

  const logout = useCallback(() => {
    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false
    });
  }, []);

  return { ...state, login, logout };
}
`,
        action: 'create'
      },
      {
        path: 'src/components/Login.tsx',
        content: `import React, { useState } from 'react';

interface LoginProps {
  onLogin: (email: string, password: string) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onLogin(email, password);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-md mx-auto">
      <div>
        <label className="block text-sm font-medium text-gray-700">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg"
        />
      </div>
      <button
        type="submit"
        className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
      >
        Login
      </button>
    </form>
  );
}
`,
        action: 'create'
      }
    ];
  }

  private generateChatFiles(): FileInfo[] {
    return [
      {
        path: 'src/types/message.ts',
        content: `export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
}
`,
        action: 'create'
      },
      {
        path: 'src/hooks/useChat.ts',
        content: `import { useState, useCallback } from 'react';
import { Message } from '../types/message';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);

  const sendMessage = useCallback((content: string) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      content,
      sender: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: crypto.randomUUID(),
        content: 'This is a simulated response.',
        sender: 'assistant',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiMessage]);
    }, 1000);
  }, []);

  return { messages, sendMessage };
}
`,
        action: 'create'
      },
      {
        path: 'src/components/Chat.tsx',
        content: `import React from 'react';
import { useChat } from '../hooks/useChat';
import MessageList from './MessageList';
import MessageInput from './MessageInput';

export default function Chat() {
  const { messages, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-[600px] border rounded-lg">
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold">Chat</h2>
      </div>
      <MessageList messages={messages} />
      <MessageInput onSend={sendMessage} />
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/MessageList.tsx',
        content: `import React from 'react';
import { Message } from '../types/message';
import MessageItem from './MessageItem';

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map(message => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/MessageItem.tsx',
        content: `import React from 'react';
import { Message } from '../types/message';

interface MessageItemProps {
  message: Message;
}

export default function MessageItem({ message }: MessageItemProps) {
  const isUser = message.sender === 'user';
  
  return (
    <div className={\`flex \${isUser ? 'justify-end' : 'justify-start'}\`}>
      <div
        className={\`max-w-[70%] p-3 rounded-lg \${
          isUser ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-900'
        }\`}
      >
        {message.content}
      </div>
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/MessageInput.tsx',
        content: `import React, { useState } from 'react';

interface MessageInputProps {
  onSend: (message: string) => void;
}

export default function MessageInput({ onSend }: MessageInputProps) {
  const [message, setMessage] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim()) {
      onSend(message.trim());
      setMessage('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t">
      <div className="flex space-x-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 px-4 py-2 border rounded-lg"
        />
        <button
          type="submit"
          className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          Send
        </button>
      </div>
    </form>
  );
}
`,
        action: 'create'
      }
    ];
  }

  private generateEcommerceFiles(): FileInfo[] {
    return [
      {
        path: 'src/types/product.ts',
        content: `export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  image: string;
  inStock: boolean;
}
`,
        action: 'create'
      },
      {
        path: 'src/hooks/useCart.ts',
        content: `import { useState, useCallback } from 'react';
import { Product } from '../types/product';

interface CartItem extends Product {
  quantity: number;
}

export function useCart() {
  const [items, setItems] = useState<CartItem[]>([]);

  const addItem = useCallback((product: Product) => {
    setItems(prev => {
      const existing = prev.find(item => item.id === product.id);
      if (existing) {
        return prev.map(item =>
          item.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...prev, { ...product, quantity: 1 }];
    });
  }, []);

  const removeItem = useCallback((productId: string) => {
    setItems(prev => prev.filter(item => item.id !== productId));
  }, []);

  const total = items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  return { items, addItem, removeItem, total };
}
`,
        action: 'create'
      },
      {
        path: 'src/components/ProductCard.tsx',
        content: `import React from 'react';
import { Product } from '../types/product';

interface ProductCardProps {
  product: Product;
  onAddToCart: (product: Product) => void;
}

export default function ProductCard({ product, onAddToCart }: ProductCardProps) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <img src={product.image} alt={product.name} className="w-full h-48 object-cover" />
      <div className="p-4">
        <h3 className="font-semibold">{product.name}</h3>
        <p className="text-gray-600 text-sm">{product.description}</p>
        <div className="mt-2 flex justify-between items-center">
          <span className="text-lg font-bold">\${product.price}</span>
          <button
            onClick={() => onAddToCart(product)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/Cart.tsx',
        content: `import React from 'react';
import { useCart } from '../hooks/useCart';

export default function Cart() {
  const { items, removeItem, total } = useCart();

  return (
    <div className="border rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4">Shopping Cart</h2>
      {items.length === 0 ? (
        <p className="text-gray-500">Your cart is empty</p>
      ) : (
        <>
          {items.map(item => (
            <div key={item.id} className="flex justify-between items-center py-2 border-b">
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-gray-500">Qty: {item.quantity}</p>
              </div>
              <div className="flex items-center space-x-2">
                <span>\${item.price * item.quantity}</span>
                <button
                  onClick={() => removeItem(item.id)}
                  className="text-red-500 hover:text-red-700"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
          <div className="mt-4 text-right">
            <span className="text-lg font-bold">Total: \${total}</span>
          </div>
        </>
      )}
    </div>
  );
}
`,
        action: 'create'
      }
    ];
  }

  private generateDashboardFiles(): FileInfo[] {
    return [
      {
        path: 'src/types/stats.ts',
        content: `export interface Stats {
  label: string;
  value: string | number;
  change?: number;
}
`,
        action: 'create'
      },
      {
        path: 'src/components/Dashboard.tsx',
        content: `import React from 'react';
import StatsCard from './StatsCard';
import Chart from './Chart';

export default function Dashboard() {
  const stats = [
    { label: 'Total Users', value: '1,234', change: 12 },
    { label: 'Revenue', value: '$45,678', change: 8 },
    { label: 'Orders', value: '890', change: -3 },
    { label: 'Conversion', value: '3.2%', change: 0.5 }
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, index) => (
          <StatsCard key={index} {...stat} />
        ))}
      </div>
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-4">Analytics</h2>
        <Chart />
      </div>
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/StatsCard.tsx',
        content: `import React from 'react';
import { Stats } from '../types/stats';

export default function StatsCard({ label, value, change }: Stats) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {change !== undefined && (
        <p className={\`text-sm mt-1 \${change >= 0 ? 'text-green-600' : 'text-red-600'}\`}>
          {change >= 0 ? '+' : ''}{change}%
        </p>
      )}
    </div>
  );
}
`,
        action: 'create'
      },
      {
        path: 'src/components/Chart.tsx',
        content: `import React from 'react';

export default function Chart() {
  return (
    <div className="h-64 flex items-center justify-center bg-gray-50 rounded">
      <p className="text-gray-500">Chart placeholder - integrate with chart library</p>
    </div>
  );
}
`,
        action: 'create'
      }
    ];
  }

  private async handleFileOperation(task: Task): Promise<AgentResult> {
    const operation = task.description.toLowerCase();
    
    // Parse operation
    if (operation.includes('delete')) {
      return this.handleDeleteOperation(task);
    } else if (operation.includes('edit')) {
      return this.handleEditOperation(task);
    } else if (operation.includes('create') || operation.includes('add')) {
      return this.handleCreateOperation(task);
    }
    
    return {
      success: false,
      error: 'Unknown file operation'
    };
  }

  private handleDeleteOperation(task: Task): AgentResult {
    // Extract file/folder path from description
    const pathMatch = task.description.match(/(?:delete|remove)\s+(.+)/i);
    if (!pathMatch) {
      return {
        success: false,
        error: 'Could not determine file path to delete'
      };
    }
    
    const path = pathMatch[1].trim();
    
    return {
      success: true,
      data: {
        operation: 'delete',
        path: path,
        message: `Confirmed: Delete ${path}?`
      }
    };
  }

  private handleEditOperation(task: Task): AgentResult {
    const pathMatch = task.description.match(/(?:edit|update|modify)\s+(.+)/i);
    if (!pathMatch) {
      return {
        success: false,
        error: 'Could not determine file path to edit'
      };
    }
    
    const path = pathMatch[1].trim();
    
    return {
      success: true,
      data: {
        operation: 'edit',
        path: path,
        message: `What changes would you like to make to ${path}?`
      }
    };
  }

  private handleCreateOperation(task: Task): AgentResult {
    const pathMatch = task.description.match(/(?:create|add)\s+(.+)/i);
    if (!pathMatch) {
      return {
        success: false,
        error: 'Could not determine file path to create'
      };
    }
    
    const path = pathMatch[1].trim();
    
    return {
      success: true,
      data: {
        operation: 'create',
        path: path,
        message: `Creating ${path}...`
      }
    };
  }
}
