/**
 * OXYCODE AI — Minimal API Types for Mini App MVP
 * Only includes types actually used by the frontend.
 */

// Image attachment types (used by prompt-box, image-upload-button, image-attachment-preview)
export interface ImageAttachment {
  id: string;
  file: File;
  preview: string;
  mimeType: string;
  size: number;
}

export const SUPPORTED_IMAGE_MIME_TYPES = [
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
] as const;

export const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
export const MAX_IMAGES_PER_MESSAGE = 4;

export function isSupportedImageType(mimeType: string): boolean {
  return (SUPPORTED_IMAGE_MIME_TYPES as readonly string[]).includes(mimeType);
}

// Auth types (used by auth-context)
export interface AuthUser {
  id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  photo_url?: string;
}

export interface SessionResponse {
  token: string;
  user: AuthUser;
}

// Model config types (used by shared components)
export interface ModelConfigsInfo {
  [key: string]: {
    modelName?: string;
    maxTokens?: number;
    temperature?: number;
  };
}

export interface AgentDisplayConfig {
  model?: string;
  provider?: string;
}

// App types (used by AppCard, AppListContainer)
export type TimePeriod = 'day' | 'week' | 'month' | 'all';
export type AppSortOption = 'newest' | 'oldest' | 'name' | 'lastUpdated';

export interface AppWithFavoriteStatus {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  isFavorite: boolean;
}

export interface GitCloneTokenData {
  token: string;
  cloneUrl: string;
}

// Feature types
export type ViewMode = 'preview' | 'code' | 'docs';
export type ProjectType = 'website' | 'miniapp' | 'telegram-bot' | 'other';
export type BehaviorType = 'agentic' | 'phasic' | 'think';

export interface FeatureDefinition {
  id: string;
  name: string;
  description: string;
  views: ViewDefinition[];
}

export interface ViewDefinition {
  id: string;
  name: string;
  icon?: string;
}

// Template types
export interface TemplateDetails {
  id: string;
  name: string;
  description: string;
  files: Record<string, string>;
}

// WebSocket types (minimal)
export interface WebSocketMessage {
  type: string;
  data?: any;
}

export type CloudflareDeploymentErrorCode = 
  | 'DEPLOYMENT_FAILED'
  | 'BUILD_FAILED'
  | 'CONFIGURATION_ERROR'
  | 'AUTH_ERROR'
  | 'QUOTA_EXCEEDED';

// Blueprint types
export interface BlueprintType {
  files: Array<{
    path: string;
    content: string;
    explanation?: string;
  }>;
  steps: string[];
}

export interface PhasicBlueprint {
  phases: Array<{
    name: string;
    files: string[];
  }>;
}

// Agent state types
export type AgentState = 'idle' | 'thinking' | 'generating' | 'deploying' | 'error';
export type PhasicState = 'planning' | 'implementing' | 'reviewing' | 'complete';

// Conversation types
export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

// File type
export interface FileType {
  filePath: string;
  fileContents: string;
  explanation?: string;
  isGenerating?: boolean;
  needsFixing?: boolean;
  hasErrors?: boolean;
  language?: string;
}

// Image attachment constants
export const SUPPORTED_IMAGE_TYPES = SUPPORTED_IMAGE_MIME_TYPES;

// Rate limit and security types (used by api-client.ts)
export interface RateLimitError {
  type: 'rate_limit';
  message: string;
  retryAfter?: number;
}

export class RateLimitExceededError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RateLimitExceededError';
  }
}

export enum SecurityErrorType {
  CSRF_VIOLATION = 'csrf_violation',
  RATE_LIMITED = 'rate_limited',
  UNAUTHORIZED = 'unauthorized',
}

export class SecurityError extends Error {
  type: SecurityErrorType;
  constructor(type: SecurityErrorType, message: string) {
    super(message);
    this.name = 'SecurityError';
    this.type = type;
  }
}
