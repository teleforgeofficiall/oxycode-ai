# Files Codemap

**Last Updated:** 2026-08-27

## Project Root

```
C:\Users\Teleforge\Desktop\OXYCODE AI BOT\
├── src/                    # React frontend (TypeScript)
├── worker/                 # Cloudflare Worker backend
├── shared/                 # Shared types and constants
├── MAIN BOT/               # Legacy Python Telegram bot
├── vibesdk/                # Cloudflare Workers SDK (reference)
├── docs/                   # Documentation
├── scripts/                # Build/setup scripts
├── public/                 # Static assets
├── package.json            # Node.js dependencies
├── vite.config.ts          # Vite build config
├── tsconfig.json           # TypeScript config
├── eslint.config.js        # ESLint config
├── vitest.config.ts        # Test config
├── ARCHITECTURE.md         # Technical architecture
├── AGENTS.md               # Agent instructions
├── CLAUDE.md               # Claude Code instructions
├── README.md               # Project overview
└── QUICKSTART.md           # Quick start guide
```

---

## src/ (React Frontend)

```
src/
├── main.tsx                          # Entry point
├── App.tsx                           # Root component
├── routes.tsx                        # Route definitions
├── api-types.ts                      # API type definitions
├── index.css                         # Global styles (Tailwind v4)
├── vite-env.d.ts                     # Vite type declarations
│
├── routes/
│   ├── home.tsx                      # Home page
│   ├── protected-route.tsx           # Auth guard
│   └── chat/
│       ├── chat.tsx                  # Main chat interface
│       ├── components/
│       │   ├── chat-input.tsx        # Message input
│       │   ├── messages.tsx          # Message list
│       │   ├── preview-iframe.tsx    # Live preview
│       │   ├── file-explorer.tsx     # File browser
│       │   ├── phase-timeline.tsx    # Agent progress
│       │   ├── deploy-panel.tsx      # Deploy controls
│       │   ├── debug-panel.tsx       # Debug viewer
│       │   ├── terminal.tsx          # Terminal output
│       │   ├── blueprint.tsx         # Blueprint display
│       │   ├── artifact-repo-viewer.tsx  # Repo viewer
│       │   ├── database-viewer.tsx   # DB inspector
│       │   ├── docs-sidebar.tsx      # Documentation
│       │   ├── export-button.tsx     # Export controls
│       │   ├── clarifying-questions-popup.tsx  # Questions
│       │   ├── thinking-indicator.tsx # Thinking animation
│       │   └── view-*.tsx            # View mode components
│       ├── hooks/
│       │   ├── use-chat.ts           # Chat state management
│       │   ├── use-debug-session.ts  # Debug session
│       │   ├── use-database-viewer.ts # DB viewer
│       │   └── use-file-content-stream.ts  # File streaming
│       ├── utils/
│       │   ├── handle-websocket-message.ts  # WS event parser
│       │   ├── message-helpers.ts    # Message utilities
│       │   ├── file-state-helpers.ts # File state
│       │   ├── websocket-helpers.ts  # WS connection
│       │   ├── tool-display.ts       # Tool output display
│       │   ├── content-detector.ts   # Content type detection
│       │   ├── deduplicate-messages.ts # Dedup logic
│       │   └── project-stage-helpers.ts # Stage detection
│       ├── contexts/
│       │   └── rollback-context.tsx   # Rollback state
│       └── mocks/
│           ├── phase-timeline-mock.ts # Mock data
│           └── file-mock.ts          # Mock files
│
├── components/
│   ├── agent-selector.tsx            # Agent type picker
│   ├── prompt-box.tsx                # Message input
│   ├── header.tsx                    # App header
│   ├── theme-toggle.tsx              # Dark/light toggle
│   ├── ErrorBoundary.tsx             # Error boundary
│   ├── browser-gate.tsx              # Browser compatibility
│   ├── maintenance-page.tsx          # Maintenance screen
│   ├── github-export-modal.tsx       # GitHub export
│   ├── image-upload-button.tsx       # Image upload
│   ├── image-attachment-preview.tsx   # Image preview
│   ├── layout/
│   │   └── app-layout.tsx            # Main layout
│   ├── ui/                           # shadcn/ui primitives
│   ├── primitives/                   # Custom primitives
│   ├── shared/                       # Shared components
│   ├── analytics/                    # Analytics components
│   ├── icons/                        # Icon components
│   ├── monaco-editor/                # Code editor
│   ├── providers/                    # Context providers
│   └── vault/                        # Vault components
│
├── contexts/
│   ├── auth-context.tsx              # Authentication state
│   ├── limits-context.tsx            # Usage limits
│   ├── theme-context.tsx             # Theme management
│   └── vault-context.tsx             # Vault state
│
├── hooks/
│   ├── useAuthGuard.ts              # Auth guard hook
│   ├── useApp.ts                    # Single app data
│   ├── useApps.ts                   # App list data
│   ├── use-profile.ts              # User profile
│   ├── use-stats.ts                # Statistics
│   ├── use-limits.ts               # Usage limits
│   ├── use-analytics.ts            # Analytics data
│   ├── use-vault.ts                # Vault operations
│   ├── use-mobile.ts               # Mobile detection
│   ├── use-auto-scroll.ts          # Auto-scroll
│   ├── use-copy-to-clipboard.ts    # Copy to clipboard
│   ├── use-drag-drop.ts            # Drag and drop
│   ├── use-github-export.ts        # GitHub export
│   ├── use-image-upload.ts         # Image upload
│   ├── use-infinite-scroll.ts      # Infinite scroll
│   ├── use-platform-status.ts      # Platform status
│   ├── use-typewriter-placeholder.ts # Typewriter effect
│   └── useSentryUser.ts            # Sentry user tracking
│
├── lib/
│   ├── api-client.ts                # HTTP client
│   ├── agent-types.ts               # Agent type definitions
│   ├── query-client.ts              # TanStack Query config
│   ├── query-keys.ts                # Query key definitions
│   ├── app-events.ts                # App event bus
│   ├── chat-api.ts                  # Chat API helpers
│   ├── cloudflare-connect.ts        # CF connection
│   ├── vault-crypto.ts              # Vault encryption
│   ├── utils.ts                     # General utilities
│   └── constants/
│       └── workflow-tabs.ts         # Workflow tab config
│
├── features/
│   ├── index.ts                     # Feature registry
│   ├── app/                         # App features
│   ├── core/                        # Core features
│   ├── general/                     # General features
│   └── presentation/               # Presentation features
│
├── utils/
│   ├── analytics.ts                 # Analytics tracking
│   ├── cloudflare-gate.ts          # CF gate check
│   ├── file-helpers.ts             # File utilities
│   ├── id-generator.ts             # ID generation
│   ├── logger.ts                   # Logging
│   ├── markdown-export.ts          # Markdown export
│   ├── model-helpers.ts            # Model utilities
│   ├── screenshot.ts               # Screenshot capture
│   ├── sentry.ts                   # Sentry config
│   ├── string.ts                   # String utilities
│   ├── usage-limit-checker.tsx     # Limit checking
│   └── ndjson-parser/
│       ├── ndjson-parser.ts        # NDJSON parsing
│       └── ndjson-parser.test.ts   # Parser tests
│
└── assets/                         # Static assets
```

---

## worker/ (Cloudflare Worker Backend)

```
worker/
├── index.ts                        # Worker entry, request router
├── app.ts                          # Hono application setup
│
├── api/
│   ├── routes/
│   │   ├── index.ts                # Route registration
│   │   ├── authRoutes.ts           # Auth endpoints
│   │   ├── appRoutes.ts            # App management
│   │   ├── userRoutes.ts           # User endpoints
│   │   ├── codegenRoutes.ts        # Agent/codegen
│   │   ├── modelConfigRoutes.ts    # Model config
│   │   ├── modelProviderRoutes.ts  # Provider keys
│   │   ├── githubExporterRoutes.ts # GitHub export
│   │   ├── statsRoutes.ts          # Statistics
│   │   ├── analyticsRoutes.ts      # Analytics
│   │   ├── cloudflareConnectRoutes.ts  # CF OAuth
│   │   ├── cloudflareAccountRoutes.ts  # CF accounts
│   │   ├── limitsRoutes.ts         # Usage limits
│   │   ├── statusRoutes.ts         # Platform status
│   │   ├── capabilitiesRoutes.ts   # Capabilities
│   │   ├── sentryRoutes.ts         # Sentry tunnel
│   │   ├── ticketRoutes.ts         # WebSocket tickets
│   │   ├── imagesRoutes.ts         # Screenshots
│   │   ├── secretsRoutes.ts        # Secrets mgmt
│   │   └── userSecretsRoutes.ts    # User secrets
│   ├── controllers/
│   │   ├── user/                   # User controller
│   │   ├── user-secrets/           # User secrets controller
│   │   ├── ticket/                 # Ticket controller
│   │   ├── status/                 # Status controller
│   │   ├── stats/                  # Stats controller
│   │   ├── sentry/                 # Sentry controller
│   │   └── secrets/                # Secrets controller
│   ├── handlers/
│   │   ├── git-protocol.ts         # Git protocol
│   │   ├── git-cache.ts            # Git caching
│   │   ├── space-preview.ts        # Space preview
│   │   └── space-preview-ratelimit.test.ts
│   ├── types/
│   │   └── route-context.ts        # Route context types
│   ├── websocketTypes.ts           # WebSocket types
│   ├── responses.ts                # Response helpers
│   └── honoAdapter.ts             # Hono adapter
│
├── agents/
│   ├── index.ts                    # Agent exports
│   ├── core/
│   │   └── codingAgent.ts          # Code generation agent
│   └── think/
│       └── ThinkAgent.ts           # Agentic think loop
│
├── database/
│   ├── index.ts                    # Database exports
│   ├── schema.ts                   # D1 schema (Drizzle)
│   ├── database.ts                 # Database connection
│   ├── types.ts                    # Database types
│   └── services/
│       ├── BaseService.ts          # Base service class
│       ├── AppService.ts           # App management
│       ├── UserService.ts          # User management
│       ├── SessionService.ts       # Session tracking
│       ├── ModelConfigService.ts   # Model config
│       ├── ModelProvidersService.ts # Provider keys
│       ├── ApiKeyService.ts        # API keys
│       ├── AnalyticsService.ts     # Analytics
│       └── AuthService.ts          # Authentication
│
├── services/
│   ├── rate-limit/
│   │   ├── rateLimits.ts           # Rate limit service
│   │   ├── DORateLimitStore.ts     # DO storage
│   │   ├── config.ts               # Rate limit config
│   │   └── errors.ts               # Rate limit errors
│   ├── csrf/
│   │   └── CsrfService.ts          # CSRF protection
│   ├── aigateway-proxy/
│   │   └── controller.ts           # AI Gateway proxy
│   ├── sandbox/
│   │   ├── request-handler.ts      # Sandbox routing
│   │   └── sandboxSdkClient.ts     # Sandbox SDK
│   └── secrets/
│       └── UserSecretsStore.ts     # User secrets DO
│
├── middleware/
│   ├── auth/
│   │   ├── auth.ts                 # Auth middleware
│   │   ├── routeAuth.ts            # Route auth config
│   │   └── ticketAuth.ts           # Ticket auth
│   └── security/
│       └── websocket.ts            # WebSocket security
│
├── config/
│   ├── index.ts                    # Config exports
│   └── security.ts                 # Security config
│
├── logger/
│   ├── index.ts                    # Logger exports
│   ├── core.ts                     # Core logger
│   └── types.ts                    # Logger types
│
├── observability/
│   └── sentry.ts                   # Sentry integration
│
├── polyfills/
│   └── safe-buffer.ts              # Buffer polyfill
│
├── types/
│   ├── appenv.ts                   # App environment
│   ├── auth-types.ts               # Auth types
│   ├── env.d.ts                    # Environment types
│   ├── image-attachment.ts         # Image types
│   └── secretsTemplates.ts         # Secret templates
│
└── utils/
    ├── authUtils.ts                # Auth utilities
    ├── cryptoUtils.ts              # Crypto utilities
    ├── jwtUtils.ts                 # JWT utilities
    ├── urls.ts                     # URL utilities
    ├── envs.ts                     # Environment detection
    ├── pathUtils.ts                # Path utilities
    ├── idGenerator.ts              # ID generation
    ├── githubUtils.ts              # GitHub utilities
    ├── deployToCf.ts               # CF deployment
    ├── dispatcherUtils.ts          # Dispatcher utils
    ├── encoding.ts                 # Encoding utils
    ├── ErrorHandling.ts            # Error handling
    ├── images.ts                   # Image processing
    ├── inputValidator.ts           # Input validation
    ├── oauthCookie.ts              # OAuth cookies
    ├── ownerPreviewToken.ts        # Owner preview tokens
    ├── passwordService.ts          # Password hashing
    ├── screenshot-security.ts      # Screenshot security
    ├── spacePreviewToken.ts        # Space preview tokens
    ├── stateSigning.ts             # State signing
    ├── timeFormatter.ts            # Time formatting
    ├── tokenEncryption.ts          # Token encryption
    ├── validationUtils.ts          # Validation
    └── wsTicketManager.ts          # WebSocket tickets
```

---

## shared/ (Shared Code)

```
shared/
├── types/
│   └── errors.ts                   # Error types (SecurityError, etc.)
└── constants/
    └── limits.ts                   # Limit constants
```

---

## MAIN BOT/ (Legacy Python)

```
MAIN BOT/
├── main.py                         # Telegram bot entry
├── config.py                       # Configuration
├── database.py                     # PostgreSQL operations
├── agent_engine.py                 # Hermes-style agent loop
├── coding_tools.py                 # 7-tool sandbox
├── payments.py                     # Telegram Stars payments
├── memory_system.py                # Triple-layer memory
├── context_engine.py               # Token tracking
├── api_server.py                   # FastAPI backend
├── cloudflare_deploy.py            # CF Pages/Workers deploy
├── cloudflare_oauth.py             # Per-user CF OAuth
├── error_fix.py                    # AI error detection
├── project_analyzer.py             # Project type detection
├── deploy_vps.py                   # SSH VPS deployment
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── SECURITY.md                     # Security docs
└── templates/
    └── cloudflare_callback.html    # OAuth callback page
```

---

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `package.json` | Root | Node.js dependencies |
| `vite.config.ts` | Root | Vite build configuration |
| `tsconfig.json` | Root | TypeScript config |
| `tsconfig.app.json` | Root | App-specific TS config |
| `tsconfig.node.json` | Root | Node-specific TS config |
| `eslint.config.js` | Root | ESLint configuration |
| `vitest.config.ts` | Root | Test configuration |
| `knip.json` | Root | Unused code detection |
| `components.json` | Root | shadcn/ui config |
| `.editorconfig` | Root | Editor settings |
| `bunfig.toml` | Root | Bun configuration |
| `wrangler.toml` | Root | Cloudflare Workers config |
| `.gitignore` | Root | Git ignore rules |
| `.env.production` | Root | Production env vars |
| `vercel.json` | Root | Vercel deployment config |

---

## Key File Locations Summary

| What | Where |
|------|-------|
| Frontend entry | `src/main.tsx` |
| Root component | `src/App.tsx` |
| Route definitions | `src/routes.tsx` |
| API types | `src/api-types.ts` |
| HTTP client | `src/lib/api-client.ts` |
| Query keys | `src/lib/query-keys.ts` |
| Chat interface | `src/routes/chat/chat.tsx` |
| Chat state | `src/routes/chat/hooks/use-chat.ts` |
| WebSocket handler | `src/routes/chat/utils/handle-websocket-message.ts` |
| Auth context | `src/contexts/auth-context.tsx` |
| Agent types | `src/lib/agent-types.ts` |
| Worker entry | `worker/index.ts` |
| Hono app | `worker/app.ts` |
| Route setup | `worker/api/routes/index.ts` |
| D1 schema | `worker/database/schema.ts` |
| Code agent | `worker/agents/core/codingAgent.ts` |
| Think agent | `worker/agents/think/ThinkAgent.ts` |
| Rate limiting | `worker/services/rate-limit/rateLimits.ts` |
| CSRF | `worker/services/csrf/CsrfService.ts` |
| Shared errors | `shared/types/errors.ts` |
| Shared limits | `shared/constants/limits.ts` |
| Python bot entry | `MAIN BOT/main.py` |
| Python agent | `MAIN BOT/agent_engine.py` |
| Documentation | `docs/CODEMAPS/` |

---

## Related Codemaps

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview and data flow
- [MODULES.md](MODULES.md) — Detailed module documentation
