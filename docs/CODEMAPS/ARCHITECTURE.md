# System Architecture Codemap

**Last Updated:** 2026-08-27
**Entry Points:** `src/main.tsx` (Frontend), `worker/index.ts` (Worker)

## Overview

OXYCODE is a full-stack AI-powered coding platform featuring a React frontend, Cloudflare Worker backend with Durable Objects, real-time WebSocket communication, and a legacy Python Telegram bot. The platform enables users to build, deploy, and ship software through AI agents.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Users                                      │
│              Browser (React SPA)              Telegram Clients          │
└──────────────────────────┬───────────────────────────┬──────────────────┘
                           │ HTTPS                     │ Bot API (polling)
                           ▼                           ▼
┌──────────────────────────────────────┐  ┌───────────────────────────────┐
│         src/ (React Frontend)        │  │      MAIN BOT/ (Python)       │
│                                      │  │                               │
│  • React 19 + React Router           │  │  • main.py (Entry point)      │
│  • TanStack Query (server state)     │  │  • agent_engine.py (AI loop)  │
│  • Tailwind CSS v4 + Kumo UI         │  │  • coding_tools.py (7 tools)  │
│  • WebSocket (real-time updates)     │  │  • database.py (PostgreSQL)   │
│  • Vite 8 (build tool)              │  │  • api_server.py (FastAPI)    │
└──────────────────────────┬───────────┘  └───────────────────────────────┘
                           │ HTTPS/WS
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    worker/ (Cloudflare Worker)                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  worker/index.ts — Request Router                                │   │
│  │  • Main domain → Hono API routes                                 │   │
│  │  • Subdomain → User app preview (sandbox/dispatch)              │   │
│  │  • OAuth routes → Cloudflare Connect                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  worker/app.ts    │  │  Durable Objects  │  │  Services         │     │
│  │  (Hono app)       │  │                  │  │                  │     │
│  │                   │  │  • CodeGenerator  │  │  • Rate Limiting │     │
│  │  • CORS/CSRF      │  │    Agent (coding)│  │  • CSRF          │     │
│  │  • Auth middleware │  │  • ThinkAgent    │  │  • AI Gateway    │     │
│  │  • Rate limiting  │  │    (agentic loop)│  │  • Sandbox       │     │
│  │  • Route setup    │  │  • SpaceDO       │  │  • Secrets       │     │
│  │                   │  │    (git-backed)  │  │  • Auth          │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  worker/database/ (D1 + Drizzle ORM)                            │   │
│  │  • Schema: worker/database/schema.ts                            │   │
│  │  • Services: UserService, AppService, SessionService, etc.      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  D1 Database │  │  KV Store    │  │  R2 Storage       │
│  (Users,     │  │  (Sessions,  │  │  (Files,          │
│   Apps,      │  │   Cache)     │  │   Artifacts)      │
│   Config)    │  │              │  │                   │
└──────────────┘  └──────────────┘  └──────────────────┘
```

## Data Flow

### 1. Frontend Authentication Flow
```
Browser → React App → AuthProvider
  → Check localStorage for JWT token
  → GET /api/auth/profile → Validate session
  → If 401 → Show auth modal
  → If valid → Set user context
```

### 2. Agent Session Flow
```
User types prompt → Chat component → apiClient.createAgentSession(args)
  → POST /api/agent (streaming response)
  → Worker routes to CodeGeneratorAgent or ThinkAgent (Durable Object)
  → Agent processes with model rotation (OpenCode Zen API)
  → WebSocket streams progress back to frontend
  → Frontend updates UI via handle-websocket-message.ts
```

### 3. App Preview Flow
```
Agent generates code → SpaceDO (git-backed files)
  → Deploy to preview subdomain (e.g., {appid}.preview.domain)
  → Worker index.ts routes subdomain requests
  → proxyToSandbox() → Live preview
  → OR dispatchToWorker() → Permanent deployment
```

### 4. Cloudflare OAuth Flow
```
User clicks "Connect Cloudflare" → /api/cloudflare/connect
  → Redirect to CF OAuth authorization
  → User authorizes → /oauth/cloudflare/callback
  → Exchange code for API token → Store in KV
  → User can now deploy to their own CF account
```

### 5. Real-time WebSocket Flow
```
Frontend connects → ws://domain/api/ws?ticket={token}
  → Worker authenticates via ticket
  → Joins agent session room
  → Receives streaming events:
    - message_chunk (AI text)
    - file_update (code changes)
    - phase_change (planning/implementing/reviewing)
    - deployment_status
  → Frontend updates via use-chat.ts hook
```

## Component Relationships

| Component | Depends On | Role |
|-----------|-----------|------|
| `src/main.tsx` | React Router | Frontend entry point |
| `src/App.tsx` | AuthProvider, LimitsProvider, ThemeProvider | Root layout with providers |
| `src/routes.tsx` | React Router | Route definitions |
| `src/lib/api-client.ts` | api-types.ts, auth-context | HTTP client for all API calls |
| `src/lib/query-keys.ts` | (none) | Centralized TanStack Query keys |
| `src/routes/chat/chat.tsx` | use-chat, WebSocket | Main chat interface |
| `src/routes/chat/hooks/use-chat.ts` | api-client, WebSocket | Chat state management |
| `src/routes/chat/utils/handle-websocket-message.ts` | (none) | WebSocket event parser |
| `worker/index.ts` | app, services, Durable Objects | Worker entry, request routing |
| `worker/app.ts` | Hono, middleware, routes | API application setup |
| `worker/api/routes/index.ts` | All route modules | Route registration |
| `worker/database/schema.ts` | Drizzle ORM | D1 database schema |
| `worker/agents/core/codingAgent.ts` | SpaceDO | Code generation agent |
| `worker/agents/think/ThinkAgent.ts` | SpaceDO | Agentic think loop |
| `shared/types/errors.ts` | (none) | Shared error types |
| `shared/constants/limits.ts` | (none) | Shared limit constants |

## Two Deployments

### React Frontend (src/)
- React 19 + React Router 7
- TanStack Query for server state
- Tailwind CSS v4 + @cloudflare/kumo UI
- Vite 8 build tool
- Deployed to Cloudflare Pages

### Cloudflare Worker (worker/)
- Hono web framework
- Durable Objects for stateful agents
- D1 database with Drizzle ORM
- KV for caching and sessions
- R2 for file storage

### Legacy Python Bot (MAIN BOT/)
- Telegram bot with polling
- PostgreSQL via psycopg2
- FastAPI Mini App backend
- Hermes-style agent loop

## External API Endpoints

| Service | Base URL | Auth | Purpose |
|---------|----------|------|---------|
| OpenCode Zen | `https://opencode.ai/zen/v1` | API key | AI model inference |
| Cloudflare API | `https://api.cloudflare.com` | OAuth tokens | Deployment, AI Gateway |
| GitHub API | `https://api.github.com` | OAuth tokens | Repository export |
| Telegram Bot API | `https://api.telegram.org` | Bot token | Legacy bot interaction |
| PostgreSQL (Neon) | Connection string | DB credentials | Legacy bot storage |

## Key Design Patterns

1. **Agent Loop** — THINK→ACT→OBSERVE cycle with model rotation
2. **Durable Objects** — Stateful agents (CodeGenerator, ThinkAgent, SpaceDO)
3. **Streaming WebSocket** — Real-time progress updates to frontend
4. **Per-User OAuth** — Each user connects their own Cloudflare account
5. **Model Rotation** — Failover across free-tier models with exponential backoff
6. **Sandboxed Execution** — Per-user filesystem isolation for code execution
7. **Git-backed Files** — SpaceDO stores app files with git history
8. **CSRF Protection** — Double-submit cookie pattern for state-changing requests
9. **Rate Limiting** — Per-user and global rate limits via Durable Objects
10. **Feature Flags** — FeatureProvider controls UI feature availability

## Related Codemaps

- [MODULES.md](MODULES.md) — Detailed module documentation
- [FILES.md](FILES.md) — Complete file listing
