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
  isAnonymous?: boolean;
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

// Analytics types
export interface UserAnalyticsResponseData {
  totalUsers: number;
  activeUsers: number;
  newUsers: number;
}

export interface AgentAnalyticsResponseData {
  totalRequests: number;
  successRate: number;
  avgResponseTime: number;
}

// App details
export interface AppDetailsData {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  files?: Record<string, string>;
  deploymentUrl?: string;
  isFavorite?: boolean;
}

// Feature definitions
export const DEFAULT_FEATURE_DEFINITIONS: FeatureDefinition[] = [];

// Vault types
export type KdfAlgorithm = 'pbkdf2' | 'argon2';

export interface SecretMetadata {
  id: string;
  name: string;
  createdAt: string;
}

export interface VaultConfigResponse {
  enabled: boolean;
  algorithm: KdfAlgorithm;
  secrets: SecretMetadata[];
}

// Platform status
export interface PlatformStatusData {
  status: 'operational' | 'degraded' | 'down';
  message?: string;
}

// Rate limit error
export interface RateLimitError {
  type: 'rate_limit';
  message: string;
  retryAfter?: number;
}

// User stats
export interface UserStats {
  totalApps: number;
  totalMessages: number;
  tokensUsed: number;
}

export interface UserActivity {
  date: string;
  messages: number;
  apps: number;
}

// WebSocket message data
export interface WebSocketMessageData {
  type: string;
  data: any;
}

// Code fix edits
export interface CodeFixEdits {
  type: string;
  filePath: string;
  oldContent: string;
  newContent: string;
}

// Agent behavior helpers
export const MAX_AGENT_QUERY_LENGTH = 10000;

export function isAgenticLikeBehavior(behavior: BehaviorType): boolean {
  return behavior === 'agentic' || behavior === 'think';
}

export function getBehaviorTypeForProject(projectType?: ProjectType): BehaviorType {
  if (projectType === 'telegram-bot') return 'think';
  return 'agentic';
}

// Rate limit error class
export class RateLimitExceededError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RateLimitExceededError';
  }
}
