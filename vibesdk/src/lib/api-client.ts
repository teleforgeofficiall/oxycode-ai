/**
 * OXYCODE AI — VPS API Client
 * Minimal client for talking to the VPS backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://153.75.247.105:8000';

interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  private async request<T = any>(
    method: string,
    path: string,
    body?: any
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  // Auth
  async authTelegram(initData: string) {
    return this.request<{ token: string; user: any }>(
      'POST',
      '/api/auth/telegram',
      { initData }
    );
  }

  async getUserMe() {
    return this.request('GET', '/api/user/me');
  }

  // Projects
  async getProjects() {
    return this.request('GET', '/api/projects');
  }

  async createProject(data: { name: string; description?: string }) {
    return this.request('POST', '/api/projects', data);
  }

  async getProject(id: string) {
    return this.request('GET', `/api/projects/${id}`);
  }

  async deleteProject(id: string) {
    return this.request('DELETE', `/api/projects/${id}`);
  }

  // Chat
  async sendMessage(data: { message: string; projectId?: number }) {
    return this.request<{ response: string; model: string; remaining: number }>(
      'POST',
      '/api/chat',
      data
    );
  }

  // Limits
  async getLimits() {
    return this.request('GET', '/api/limits');
  }

  // Deploy
  async deploy(data: { project_id: string; subdomain?: string }) {
    return this.request('POST', '/api/deploy', data);
  }

  // Fix
  async fixError(data: { error: string; project_id?: string }) {
    return this.request('POST', '/api/fix', data);
  }

  async applyFix(data: { fix: any; project_id: string }) {
    return this.request('POST', '/api/fix/apply', data);
  }

  // Health
  async health() {
    return this.request('GET', '/api/health');
  }
}

export const apiClient = new ApiClient();
export type { ApiResponse };

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
