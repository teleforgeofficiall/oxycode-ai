# Modules Codemap

**Last Updated:** 2026-08-27

## Module Dependency Graph

```
                          shared/
                     ┌───────┴───────┐
                     │ types/errors  │
                     │ constants/    │
                     └───────┬───────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌──────────┐       ┌──────────┐       ┌──────────┐
   │  src/    │       │ worker/  │       │ MAIN BOT/│
   │ (React)  │       │ (CF Work)│       │ (Python) │
   └────┬─────┘       └────┬─────┘       └────┬─────┘
        │                  │                  │
        │                  │                  │
   Frontend            Backend             Legacy
```

---

## 1. Frontend Modules (src/)

### 1.1 Application Core

#### src/main.tsx
**Purpose:** React entry point. Creates browser router and renders app.

**Location:** `src/main.tsx`

**Key Exports:** None (entry point)

**Dependencies:** React Router, App component

---

#### src/App.tsx
**Purpose:** Root application component with provider hierarchy.

**Location:** `src/App.tsx`

**Provider Stack (top to bottom):**
```
ErrorBoundary
  → GlobalErrorCatcher
    → PersistQueryClientProvider (TanStack Query)
      → ThemeProvider
        → AuthProvider
          → LimitsProvider
            → ToastProvider (Kumo)
              → FeatureProvider
                → BrowserGate
                  → AppInner (layout + Outlet)
```

**Key Features:**
- Maintenance mode detection (shows MaintenancePage for non-admins)
- Global error catching (uncaught errors, unhandled rejections)
- Persistent query client with offline support

**Dependencies:** auth-context, limits-context, theme-context, features, query-client

---

#### src/routes.tsx
**Purpose:** Route definitions for React Router.

**Location:** `src/routes.tsx`

**Routes:**
| Path | Component | Auth Required |
|------|-----------|---------------|
| `/` | Home | No |
| `/profile` | Settings | Yes |
| `/chat/:chatId` | Chat | Yes |
| `/settings` | Redirect to /profile | No |

**Dependencies:** App, Home, Chat, Settings, ProtectedRoute

---

### 1.2 API Layer

#### src/api-types.ts
**Purpose:** TypeScript types for all frontend-backend communication.

**Location:** `src/api-types.ts`

**Key Types:**
| Type | Purpose |
|------|---------|
| `ImageAttachment` | Image upload data |
| `AuthUser` | Authenticated user info |
| `SessionResponse` | Auth session response |
| `CodeGenArgs` | Agent session creation args |
| `FileType` | Generated file metadata |
| `AgentState` | Agent UI state |
| `BehaviorType` | Agent behavior mode |
| `WebSocketMessage` | WebSocket event format |
| `RateLimitError` | Rate limit error data |
| `SecurityError` | Security violation error |

**Constants:**
- `MAX_AGENT_QUERY_LENGTH` (10000)
- `MAX_IMAGE_SIZE_BYTES` (10MB)
- `MAX_IMAGES_PER_MESSAGE` (4)
- `SUPPORTED_IMAGE_MIME_TYPES` (png, jpeg, gif, webp)

---

#### src/lib/api-client.ts
**Purpose:** Unified HTTP client for all worker API calls.

**Location:** `src/lib/api-client.ts`

**Key Features:**
- Automatic JWT auth via localStorage
- CSRF token management (double-submit pattern)
- 401 interception for auth modals
- Rate limit error handling
- Streaming response support

**API Methods:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `getProfile()` | GET /api/auth/profile | Current user |
| `getUserApps()` | GET /api/apps | User's apps |
| `createApp()` | POST /api/apps | Create app |
| `createAgentSession()` | POST /api/agent | Start agent (streaming) |
| `connectToAgent()` | GET /api/agent/:id/connect | Reconnect to agent |
| `deployPreview()` | POST /api/agent/:id/preview | Deploy app |
| `getModelConfigs()` | GET /api/model-configs | AI model settings |
| `connectCloudflare()` | POST /api/cloudflare/connect | CF OAuth |

**Dependencies:** api-types, auth-context, sonner (toast)

---

#### src/lib/query-keys.ts
**Purpose:** Centralized TanStack Query key definitions.

**Location:** `src/lib/query-keys.ts`

**Key Hierarchies:**
```typescript
queryKeys.apps.all        // All apps queries
queryKeys.apps.detail(id) // Single app
queryKeys.user.profile    // User profile
queryKeys.user.stats      // User statistics
queryKeys.modelConfigs    // Model configurations
```

---

### 1.3 State Management

#### src/contexts/auth-context.tsx
**Purpose:** Authentication state and JWT token management.

**Location:** `src/contexts/auth-context.tsx`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `AuthProvider` | Component | Context provider |
| `useAuth()` | Hook | Access auth state |

**Auth State:**
- `user` — Current AuthUser or null
- `isLoading` — Auth check in progress
- `isMaintenance` — Maintenance mode active
- `isAdmin` — Current user is admin

**Dependencies:** api-client, App.tsx

---

#### src/contexts/limits-context.tsx
**Purpose:** Usage limits and Cloudflare credits tracking.

**Location:** `src/contexts/limits-context.tsx`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `LimitsProvider` | Component | Context provider |
| `useLimits()` | Hook | Access limits state |

---

#### src/contexts/theme-context.tsx
**Purpose:** Dark/light theme management.

**Location:** `src/contexts/theme-context.tsx`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `ThemeProvider` | Component | Context provider |
| `useTheme()` | Hook | Access theme state |

---

### 1.4 Chat System

#### src/routes/chat/chat.tsx
**Purpose:** Main chat interface with agent interaction.

**Location:** `src/routes/chat/chat.tsx`

**Key Components:**
- `ChatInput` — User message input with image upload
- `Messages` — Conversation history display
- `PreviewIframe` — Live app preview
- `FileExplorer` — Generated file browser
- `PhaseTimeline` — Agent progress display
- `DeployPanel` — Deployment controls
- `DebugPanel` — Debug session viewer

**Dependencies:** use-chat, handle-websocket-message, api-client

---

#### src/routes/chat/hooks/use-chat.ts
**Purpose:** Chat state management and WebSocket connection.

**Location:** `src/routes/chat/hooks/use-chat.ts`

**Key Features:**
- WebSocket connection management
- Message history state
- Agent state tracking (idle/thinking/generating/deploying)
- File updates from agent
- Deployment status

**Returns:**
```typescript
{
  messages: Message[];
  agentState: AgentState;
  files: FileType[];
  sendMessage: (text: string, images?: ImageAttachment[]) => void;
  connect: (agentId: string) => void;
  disconnect: () => void;
}
```

---

#### src/routes/chat/utils/handle-websocket-message.ts
**Purpose:** Parse and route WebSocket events from agent.

**Location:** `src/routes/chat/utils/handle-websocket-message.ts`

**Event Types:**
| Event | Purpose |
|-------|---------|
| `message_chunk` | Streaming AI text |
| `file_update` | Code file changes |
| `phase_change` | Agent phase transition |
| `deployment_status` | Deploy progress |
| `error` | Agent error |

---

### 1.5 Shared Components

#### src/components/agent-selector.tsx
**Purpose:** Agent type selection (OXYGENT, Debugger, Architect, Designer).

**Location:** `src/components/agent-selector.tsx`

**Dependencies:** agent-types.ts

---

#### src/components/prompt-box.tsx
**Purpose:** Message input with image upload and send button.

**Location:** `src/components/prompt-box.tsx`

---

#### src/components/layout/
**Purpose:** App layout components (sidebar, header, content area).

**Location:** `src/components/layout/`

**Key Components:**
- `AppLayout` — Main layout wrapper
- `Sidebar` — Navigation sidebar

---

### 1.6 Feature Modules

#### src/features/
**Purpose:** Feature-gated UI modules.

**Location:** `src/features/`

**Feature Groups:**
| Feature | Purpose |
|---------|---------|
| `app/` | App management features |
| `core/` | Core platform features |
| `general/` | General UI features |
| `presentation/` | App presentation/display |

---

## 2. Backend Modules (worker/)

### 2.1 Core

#### worker/index.ts
**Purpose:** Worker entry point and request router.

**Location:** `worker/index.ts`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `default` | ExportedHandler | Main fetch handler |
| `CodeGeneratorAgent` | Durable Object | Code generation |
| `ThinkAgent` | Durable Object | Agentic think loop |
| `SpaceDO` | Durable Object | Git-backed file storage |
| `DORateLimitStore` | Durable Object | Rate limit storage |
| `UserSecretsStore` | Durable Object | User secrets |

**Request Routing:**
```
Main domain (CUSTOM_DOMAIN)
  → /api/* → Hono app (worker/app.ts)
  → /oauth/* → OAuth handlers
  → /apps/:id.git/* → Git protocol
  → /* → Static assets (ASSETS binding)

Subdomain ({app}.preview.domain)
  → proxyToSandbox() → Live preview
  → dispatchToWorker() → Permanent deployment
```

---

#### worker/app.ts
**Purpose:** Hono application with middleware and route setup.

**Location:** `worker/app.ts`

**Middleware Stack:**
1. Secure headers (except WebSocket, OAuth)
2. CORS (for /api/*)
3. CSRF protection (double-submit pattern)
4. Global rate limiting
5. Auth (ownerOnly by default)

**Dependencies:** Hono, cors, secure-headers, CsrfService, RateLimitService

---

### 2.2 API Routes

#### worker/api/routes/index.ts
**Purpose:** Route registration for all API endpoints.

**Location:** `worker/api/routes/index.ts`

**Route Groups:**
| Route File | Prefix | Purpose |
|------------|--------|---------|
| `authRoutes.ts` | /api/auth/* | Login, register, OAuth, sessions |
| `appRoutes.ts` | /api/apps/* | App CRUD, favorites, visibility |
| `userRoutes.ts` | /api/user/* | Profile, settings, providers |
| `codegenRoutes.ts` | /api/agent/* | Agent sessions, streaming |
| `modelConfigRoutes.ts` | /api/model-configs/* | AI model configuration |
| `modelProviderRoutes.ts` | /api/user/providers/* | BYOK provider management |
| `githubExporterRoutes.ts` | /api/github-app/* | GitHub export |
| `statsRoutes.ts` | /api/stats/* | User statistics |
| `analyticsRoutes.ts` | /api/*/analytics/* | AI Gateway analytics |
| `cloudflareConnectRoutes.ts` | /api/cloudflare/* | CF OAuth flow |
| `cloudflareAccountRoutes.ts` | /api/cloudflare/* | CF account management |
| `limitsRoutes.ts` | /api/limits | Usage limits |
| `statusRoutes.ts` | /api/status | Platform status |
| `capabilitiesRoutes.ts` | /api/capabilities | Feature capabilities |
| `sentryRoutes.ts` | /api/sentry/* | Error reporting tunnel |
| `ticketRoutes.ts` | /api/tickets/* | WebSocket tickets |
| `imagesRoutes.ts` | /api/screenshots/* | Screenshot serving |

---

### 2.3 Database

#### worker/database/schema.ts
**Purpose:** D1 database schema definitions (Drizzle ORM).

**Location:** `worker/database/schema.ts`

**Tables:**
| Table | Purpose |
|-------|---------|
| `users` | User accounts |
| `apps` | Generated applications |
| `app_files` | App source files |
| `sessions` | User sessions |
| `model_configs` | AI model configurations |
| `model_providers` | BYOK provider keys |
| `deployments` | Deployment records |
| `analytics` | AI Gateway usage |
| `rate_limits` | Rate limit tracking |

---

#### worker/database/services/
**Purpose:** Database service layer for business logic.

**Location:** `worker/database/services/`

**Services:**
| Service | Purpose |
|---------|---------|
| `AppService.ts` | App CRUD, visibility, ownership |
| `UserService.ts` | User management |
| `SessionService.ts` | Session tracking |
| `ModelConfigService.ts` | Model configuration |
| `ModelProvidersService.ts` | Provider key management |
| `ApiKeyService.ts` | API key management |
| `AnalyticsService.ts` | Usage analytics |
| `AuthService.ts` | Authentication |

---

### 2.4 Durable Objects

#### worker/agents/core/codingAgent.ts
**Purpose:** Code generation agent with tool execution.

**Location:** `worker/agents/core/codingAgent.ts`

**Key Features:**
- Model rotation (OpenCode Zen API)
- File generation and updates
- Tool calling (read, write, patch, terminal)
- Streaming WebSocket progress

---

#### worker/agents/think/ThinkAgent.ts
**Purpose:** Agentic think loop for complex tasks.

**Location:** `worker/agents/think/ThinkAgent.ts`

**Key Features:**
- Multi-step planning
- Iterative code generation
- SpaceDO integration for file storage
- Browser automation tools

---

#### @space-do/space (SpaceDO)
**Purpose:** Git-backed file storage for generated apps.

**Location:** `@space-do/space` (npm package)

**Key Features:**
- Git commit history for app files
- Branch management
- Preview URL generation
- Deploy to permanent workers

---

### 2.5 Services

#### worker/services/rate-limit/
**Purpose:** Rate limiting via Durable Objects.

**Location:** `worker/services/rate-limit/`

**Key Exports:**
- `RateLimitService` — Global and per-user rate limiting
- `DORateLimitStore` — Durable Object storage

---

#### worker/services/csrf/
**Purpose:** CSRF token generation and validation.

**Location:** `worker/services/csrf/`

**Key Exports:**
- `CsrfService` — Double-submit cookie pattern

---

#### worker/services/aigateway-proxy/
**Purpose:** Proxy requests to Cloudflare AI Gateway.

**Location:** `worker/services/aigateway-proxy/`

**Key Exports:**
- `proxyToAiGateway` — Forward inference requests

---

#### worker/services/sandbox/
**Purpose:** Sandboxed code execution for user apps.

**Location:** `worker/services/sandbox/`

**Key Exports:**
- `proxyToSandbox` — Route to live sandbox
- `UserAppSandboxService` — Sandbox management

---

### 2.6 Middleware

#### worker/middleware/auth/
**Purpose:** Authentication and authorization middleware.

**Location:** `worker/middleware/auth/`

**Key Exports:**
- `auth` — JWT/cookie authentication
- `routeAuth` — Route-level auth config
- `ticketAuth` — WebSocket ticket auth

---

### 2.7 Utilities

#### worker/utils/
**Purpose:** Shared utility functions.

**Location:** `worker/utils/`

**Key Utilities:**
| File | Purpose |
|------|---------|
| `authUtils.ts` | Authentication helpers |
| `cryptoUtils.ts` | Encryption/decryption |
| `jwtUtils.ts` | JWT token handling |
| `urls.ts` | URL construction |
| `envs.ts` | Environment detection |
| `pathUtils.ts` | Path manipulation |
| `idGenerator.ts` | Unique ID generation |
| `githubUtils.ts` | GitHub API helpers |
| `deployToCf.ts` | Cloudflare deployment |

---

## 3. Shared Modules (shared/)

### shared/types/errors.ts
**Purpose:** Error types shared between frontend and backend.

**Location:** `shared/types/errors.ts`

**Key Types:**
| Type | Purpose |
|------|---------|
| `SecurityErrorType` | Error classification enum |
| `SecurityError` | Base security error class |
| `RateLimitExceededError` | Rate limit violation |
| `UsageLimitExceededError` | Free tier limit exceeded |

---

### shared/constants/limits.ts
**Purpose:** Limit constants shared between frontend and backend.

**Location:** `shared/constants/limits.ts`

**Constants:**
| Constant | Value | Purpose |
|----------|-------|---------|
| `MINIMUM_CLOUDFLARE_BALANCE` | $2.00 | Minimum CF balance |
| `CREDITS_BANNER_THRESHOLD` | $10 | Banner visibility threshold |

**Functions:**
- `hasMinimumBalance()` — Check CF balance
- `canProceedWithRequest()` — Validate limits

---

## 4. Legacy Modules (MAIN BOT/)

### Python Bot Modules
**Purpose:** Original Telegram bot (legacy, maintained but not primary).

**Location:** `MAIN BOT/`

| Module | Purpose |
|--------|---------|
| `main.py` | Telegram bot entry, handlers |
| `config.py` | Environment variables |
| `database.py` | PostgreSQL operations |
| `agent_engine.py` | Hermes-style agent loop |
| `coding_tools.py` | 7-tool sandbox |
| `payments.py` | Telegram Stars payments |
| `memory_system.py` | Triple-layer memory |
| `context_engine.py` | Token tracking |
| `api_server.py` | FastAPI Mini App backend |
| `cloudflare_deploy.py` | CF Pages/Workers deploy |
| `cloudflare_oauth.py` | Per-user CF OAuth |
| `error_fix.py` | AI error detection |
| `project_analyzer.py` | Project type detection |
| `deploy_vps.py` | SSH VPS deployment |

---

## Cross-Module Relationships

```
src/ (Frontend)
  ├── api-client.ts ───────→ worker/api/* (HTTP)
  ├── use-chat.ts ─────────→ worker WebSocket (WS)
  ├── auth-context.tsx ────→ apiClient.getProfile()
  └── query-keys.ts ───────→ TanStack Query cache

worker/ (Backend)
  ├── app.ts ──────────────→ routes/* → controllers/* → services/*
  ├── index.ts ────────────→ app.ts, sandbox, dispatch
  ├── agents/* ────────────→ SpaceDO, AI Gateway
  └── database/* ──────────→ D1 (Drizzle ORM)

shared/ (Shared)
  ├── types/errors.ts ─────→ worker/services/*, src/api-client.ts
  └── constants/limits.ts ─→ worker/limits/*, src/limits-context.tsx
```

## Related Codemaps

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview and data flow
- [FILES.md](FILES.md) — Complete file listing
