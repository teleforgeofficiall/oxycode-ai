# Files Codemap

**Last Updated:** 2026-08-21

## Project Root

```
C:\Users\Teleforge\Desktop\OXYCODE AI BOT\
├── README.md                    # Project overview and setup
├── .gitignore                   # Git ignore rules
│
├── MAIN BOT/                    # Production bot deployment (18 files)
├── vibesdk/                     # Cloudflare Workers SDK (active)
├── vibesdk-read/                # Cloudflare Workers SDK (read-only reference)
└── docs/                        # Documentation (codemaps)
```

---

## MAIN BOT/

Production deployment of OXYGENT Telegram bot with full feature set.

| File | Lines | Purpose | Key Exports |
|------|-------|---------|-------------|
| `main.py` | 459 | Entry point, Telegram handlers, admin panel | Command/callback handlers, bot setup |
| `config.py` | 210 | Environment variables, AI models, messages | `BOT_TOKEN`, `ADMIN_IDS`, `OPENCODE_ZEN_*`, `SYSTEM_PROMPT` |
| `database.py` | 1348 | PostgreSQL operations, connection pooling | `_POOL`, `get_user()`, `add_user()`, `save_payment()` |
| `agent_engine.py` | 664 | Hermes-style AI agent loop | `agent_build()` |
| `coding_tools.py` | 775 | 7-tool sandbox for code/file operations | `read_file()`, `write_file()`, `terminal()`, `web_search()` |
| `payments.py` | 101 | Telegram Stars payment processing | `STAR_PACKAGES`, `get_buy_keyboard()`, `handle_successful_payment()` |
| `memory_system.py` | 509 | Triple-layer memory (file + DB + unified) | `HermesMemory`, `MemoryDatabase`, `OxygentMemory`, `get_memory()` |
| `context_engine.py` | 159 | Token tracking, auto-compaction | `ContextEngine` |
| `api_server.py` | 833 | FastAPI Mini App backend | All `/api/*` endpoints |
| `cloudflare_deploy.py` | 349 | CF Pages/Workers deployment | `deploy_to_pages()`, `deploy_to_workers()` |
| `cloudflare_oauth.py` | 345 | Per-user CF OAuth token management | `cf_api_get()`, `cf_api_post()`, `get_cloudflare_account()` |
| `error_fix.py` | 232 | AI-powered error detection and auto-repair | `build_fix_prompt()`, `analyze_error()` |
| `project_analyzer.py` | 330 | Auto-detect project type from prompt | `analyze_prompt()` |
| `deploy_vps.py` | 186 | SSH-based VPS deployment | `connect_vps()`, `deploy()` |
| `requirements.txt` | 12 | Python dependencies | `python-telegram-bot`, `psycopg2`, `aiohttp`, `fastapi`, `pyjwt` |
| `templates/cloudflare_callback.html` | - | Cloudflare OAuth callback page | - |
| `.env` | - | Environment variables (not in git) | - |
| `.env.example` | 26 | Example environment config | - |
| `SECURITY.md` | 91 | Security documentation | - |

### main.py — Handler Structure

```
main.py (459 lines)
├── Imports (telegram, config, database)
├── Constants (MINI_APP_URL, MAINTENANCE_MSG)
├── Helper Functions
│   ├── is_admin(user_id) → bool
│   ├── is_maintenance_mode() → bool
│   ├── notify_admins(bot, text)
│   └── _entities_to_list(entities)
├── Command Handlers
│   ├── /start — Welcome message, Mini App button
│   ├── /admin — Admin panel (maintenance toggle, stats)
│   ├── /selftest — Health check
│   └── (future: /menu, /create, /status, /voice, etc.)
├── Callback Handlers
│   ├── admin_toggle_maintenance — Toggle maintenance mode
│   ├── admin_stats — Show bot statistics
│   └── (future: session, payment callbacks)
├── Message Handlers
│   └── Non-command messages → maintenance check
├── Bot Setup
│   └── Application builder, handler registration
└── Main
    └── Application.run_polling()
```

### api_server.py — Endpoint Structure

```
api_server.py (833 lines)
├── Config (BOT_TOKEN, JWT_SECRET, OPENCODE_ZEN_*)
├── Middleware
│   ├── CORS (allow all origins for dev)
│   └── MaintenanceMiddleware (blocks non-admins when maintenance ON)
├── Auth Endpoints
│   ├── POST /api/auth/telegram — Verify initData, return JWT
│   └── GET /api/user/me — Get current user profile
├── Project Endpoints
│   ├── GET /api/projects — List user's projects
│   ├── POST /api/projects — Create new project
│   ├── GET /api/projects/:id — Get project details
│   └── DELETE /api/projects/:id — Delete project
├── AI Endpoints
│   ├── POST /api/chat — Send message to AI
│   └── GET /api/limits — Get daily limits
├── Deployment Endpoints
│   ├── POST /api/deploy — Deploy to Cloudflare
│   ├── POST /api/fix — AI error analysis
│   ├── POST /api/fix/apply — Apply fixes and redeploy
│   └── GET /api/deployments — List deployed projects
├── Cloudflare OAuth Endpoints
│   ├── GET /api/cloudflare/status — Check connection
│   ├── GET /api/cloudflare/auth-url — Get auth URL
│   ├── GET /api/cloudflare/callback — Handle callback
│   └── DELETE /api/cloudflare/disconnect — Disconnect account
└── Main
    └── uvicorn.run()
```

---

## vibesdk/

Cloudflare Workers SDK for the OXYCODE platform.

```
vibesdk/
├── worker/                    # Main worker code
│   ├── utils/                 # Utility modules
│   │   ├── authUtils.ts       # Authentication
│   │   ├── cryptoUtils.ts     # Encryption
│   │   ├── deployToCf.ts      # CF deployment
│   │   ├── dispatcherUtils.ts # Request dispatching
│   │   ├── encoding.ts        # Encoding utils
│   │   ├── envs.ts            # Environment config
│   │   ├── ErrorHandling.ts   # Error handling
│   │   ├── githubUtils.ts     # GitHub integration
│   │   ├── idGenerator.ts     # ID generation
│   │   ├── images.ts          # Image processing
│   │   ├── inputValidator.ts  # Input validation
│   │   ├── jwtUtils.ts        # JWT handling
│   │   ├── oauthCookie.ts     # OAuth cookies
│   │   ├── ownerPreviewToken.ts
│   │   ├── passwordService.ts # Password hashing
│   │   ├── pathUtils.ts       # Path utilities
│   │   ├── screenshot-security.ts
│   │   ├── spacePreviewToken.ts
│   │   ├── stateSigning.ts    # State signing
│   │   ├── timeFormatter.ts   # Time formatting
│   │   ├── tokenEncryption.ts # Token encryption
│   │   ├── urls.ts            # URL utilities
│   │   ├── validationUtils.ts # Validation
│   │   └── wsTicketManager.ts # WebSocket tickets
│   ├── types/                 # TypeScript types
│   │   ├── appenv.ts          # App environment
│   │   ├── auth-types.ts      # Auth types
│   │   ├── env.d.ts           # Environment types
│   │   ├── image-attachment.ts
│   │   └── secretsTemplates.ts
│   └── services/              # Service modules
│       └── static-analysis/   # Code analysis
├── container/                 # Container management
│   ├── cli-tools.ts
│   ├── process-monitor.ts
│   ├── storage.ts
│   └── types.ts
├── packages/                  # Shared packages
│   └── artifacts-viewer/      # Artifact viewer UI
├── scripts/                   # Build/deploy scripts
│   ├── deploy.ts
│   ├── dev-browser-sidecar.ts
│   ├── setup.ts
│   └── undeploy.ts
├── migrations/                # Database migrations
├── docs/                      # API documentation
├── debug-tools/               # Debug utilities
├── package.json
├── drizzle.config.local.ts
└── drizzle.config.remote.ts
```

---

## docs/

Documentation directory.

```
docs/
└── CODEMAPS/
    ├── ARCHITECTURE.md    # System overview, data flow, diagrams
    ├── MODULES.md         # Module docs, APIs, dependencies
    └── FILES.md           # This file
```

---

## Data Directories (Runtime)

Created at runtime, not in git.

| Path | Purpose | Format |
|------|---------|--------|
| `/tmp/oxygent_sandbox/{uid}/{sid}/` | Per-user session sandboxes | Files |
| `./memory/` | HermesMemory file storage | `{telegram_id}/MEMORY.md`, `USER.md` |
| `./data/` | SQLite databases | `memory.db`, `tools.db` |
| `./.agent/` | Agent working state | Various |
| `./logs/` | Application logs | `.log` files |

---

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `.gitignore` | Project root | Git ignore rules |
| `.env` | Each bot | Environment variables (not in git) |
| `.env.example` | MAIN BOT | Example environment config |
| `requirements.txt` | Each bot | Python package dependencies |
| `SECURITY.md` | MAIN BOT | Security documentation |
| `CLAUDE.md` | Project root | Claude Code session instructions |

---

## Key File Locations Summary

| What | Where |
|------|-------|
| Telegram bot entry | `MAIN BOT/main.py` |
| Mini App API backend | `MAIN BOT/api_server.py` |
| All config | `*/config.py` |
| Database layer | `*/database.py` |
| AI agent loop | `*/agent_engine.py` |
| Tool sandbox | `*/coding_tools.py` |
| Payment system | `*/payments.py` |
| Memory (file) | `*/memory_system.py` → `./memory/` |
| Memory (SQLite) | `*/memory_system.py` → `./data/memory.db` |
| Token tracking | `MAIN BOT/context_engine.py` |
| CF OAuth | `MAIN BOT/cloudflare_oauth.py` |
| CF Deployment | `MAIN BOT/cloudflare_deploy.py` |
| Error fixing | `MAIN BOT/error_fix.py` |
| Project detection | `MAIN BOT/project_analyzer.py` |
| VPS deployment | `MAIN BOT/deploy_vps.py` |
| Cloudflare Workers | `vibesdk/` |
| Documentation | `docs/CODEMAPS/` |

---

## Related Codemaps

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview and data flow
- [MODULES.md](MODULES.md) — Detailed module documentation
