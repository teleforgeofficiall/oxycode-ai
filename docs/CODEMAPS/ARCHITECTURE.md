# System Architecture Codemap

**Last Updated:** 2026-08-21
**Entry Points:** `MAIN BOT/main.py`, `MAIN BOT/api_server.py`, `CLONE BOT/main.py`

## Overview

OXYGENT is a Telegram bot + Mini App platform providing AI-powered coding assistance. It features a Hermes-style agent loop, sandboxed code execution, Cloudflare deployment with per-user OAuth, credit-based payments, and a FastAPI backend for the web dashboard.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Users                                       │
│          Telegram Client              Browser (Mini App)            │
└──────────────┬──────────────────────────────┬───────────────────────┘
               │ Bot API (polling)            │ HTTPS (REST API)
               ▼                              ▼
┌──────────────────────────┐   ┌──────────────────────────────────────┐
│      main.py             │   │         api_server.py                 │
│  (Telegram Bot Gateway)  │   │    (FastAPI Mini App Backend)        │
│                          │   │                                      │
│  • Command routing       │   │  • JWT auth (/api/auth/telegram)     │
│  • Callback handling     │   │  • Project CRUD (/api/projects)      │
│  • Admin panel (/admin)  │   │  • AI chat proxy (/api/chat)         │
│  • Maintenance mode      │   │  • Deploy proxy (/api/deploy)        │
│  • Mini App launcher     │   │  • Error fix (/api/fix)              │
└──────────┬───────────────┘   └──────────┬───────────────────────────┘
           │                              │
           └──────────────┬───────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│agent_engine  │  │coding_tools  │  │ memory_system    │
│              │  │              │  │                  │
│ • Agent Loop │  │ • read_file  │  │ • HermesMemory   │
│ • Model Rot  │  │ • write_file │  │   (file-based)   │
│ • Sandboxed  │  │ • search     │  │ • MemoryDatabase │
│   Execution  │  │ • patch      │  │   (SQLite)       │
│ • Approval   │  │ • terminal   │  │ • OxygentMemory  │
│   System     │  │ • exec_code  │  │   (unified)      │
└──────┬───────┘  │ • web_search │  └────────┬─────────┘
       │          └──────────────┘           │
       ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        database.py                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Connection Pool (psycopg2 SimpleConnectionPool)            │   │
│  │  • 5-50 connections, automatic validation & recycling       │   │
│  │  • Schema isolation (public for prod, clone for staging)    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  Tables: users, channels, user_states, code_sessions,              │
│          payments, broadcasts, settings, deployments,              │
│          projects, daily_messages, cloudflare_accounts              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ SQL (TLS)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   PostgreSQL (Neon DB)                               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    Deployment Layer                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ cloudflare_      │  │ cloudflare_      │  │ deploy_vps.py    │  │
│  │ oauth.py         │  │ deploy.py        │  │                  │  │
│  │                  │  │                  │  │ SSH paramiko     │  │
│  │ Per-user OAuth   │  │ Pages + Workers  │  │ Upload bot + API │  │
│  │ token management │  │ file deployment  │  │ to VPS           │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Telegram Bot Flow
```
User sends message → main.py handlers → extract user info
  → database.get_user(user_id) → Check maintenance mode
    → If admin: proceed
    → If non-admin + maintenance: show maintenance message
  → Route to appropriate handler:
    → /create → Code session management
    → /voice → TTS
    → /search → Web search
    → /explain, /fix → AI-powered code analysis
    → Text in session → agent_engine.agent_build()
```

### 2. Mini App Flow
```
Browser → api_server.py → Verify Telegram initData → JWT auth
  → /api/projects → CRUD operations via database.py
  → /api/chat → Proxy to OpenCode Zen API
  → /api/deploy → cloudflare_deploy.py → Live URL
  → /api/fix → error_fix.py → AI analysis → Auto-repair
```

### 3. Agent Loop Flow (agent_engine.py)
```
agent_build(uid, sid, user_message)
  → Create sandbox at /tmp/oxygent_sandbox/{uid}/{sid}/
  → Build system prompt with tools + context
  → Select model (primary: mimo-v2.5-free)
  → Send to OpenCode Zen API
  → Parse response for tool_calls
  → Execute tool in sandbox → Feed result back
  → Loop (max 8 turns) until: no tool_calls / timeout / approval needed
  → Collect all files → Return {ok, files, summary}
```

### 4. Payment Flow (payments.py)
```
User taps "Buy Credits" → Show package options
  → User selects → send_invoice() with Telegram Stars
  → PreCheckoutQuery → answer_ok=True
  → SuccessfulPayment → Check charge_id uniqueness
    → Save to payments table → Add bonus_messages to user
    → Send confirmation
```

### 5. Cloudflare Deployment Flow
```
Agent calls deploy_website/deploy_bot tool
  → cloudflare_deploy.py
    → Get user's CF token from database (cloudflare_accounts table)
    → If Pages: POST /accounts/{id}/pages/projects → Upload zip
    → If Workers: PUT /accounts/{id}/workers/scripts/{name}
    → Return live URL
```

### 6. Error Fix Flow
```
User clicks "Fix" in Mini App
  → /api/fix → error_fix.py
    → Build fix prompt with error + project files
    → Send to OpenCode AI for analysis
    → Parse AI response for fixes
    → If autoFixable: /api/fix/apply → Re-deploy to Cloudflare
    → Return fix result to frontend
```

## Component Relationships

| Component | Depends On | Role |
|-----------|-----------|------|
| `main.py` | All modules | Telegram bot entry point, command/callback routing |
| `api_server.py` | `database`, `config`, `error_fix`, `cloudflare_oauth`, `cloudflare_deploy` | FastAPI Mini App backend |
| `config.py` | (none) | Environment variables, AI models, messages, limits |
| `database.py` | `config.py` | PostgreSQL CRUD, connection pooling, schema isolation |
| `agent_engine.py` | `config`, `coding_tools` | AI agent loop, model rotation, sandboxed execution |
| `coding_tools.py` | (none) | 7-tool sandbox (file ops, terminal, web search) |
| `payments.py` | `database.py` | Telegram Stars payments, credit management |
| `memory_system.py` | (none) | Triple-layer memory (file + SQLite + unified) |
| `context_engine.py` | (none) | Token tracking, auto-compaction (MAIN BOT) |
| `tools.py` | (none) | Alternate SQLite memory system (CLONE BOT) |
| `cloudflare_oauth.py` | `database.py` | Per-user Cloudflare OAuth token management |
| `cloudflare_deploy.py` | `cloudflare_oauth.py` | Deploy to CF Pages/Workers using user tokens |
| `error_fix.py` | `config.py` | AI-powered error detection and auto-repair |
| `project_analyzer.py` | (none) | Auto-detect project type/stack from prompt |
| `deploy_vps.py` | (none) | SSH-based VPS deployment (paramiko) |

## Two Deployments

### MAIN BOT
- Full production deployment with all modules
- 18 Python files (including API server, Cloudflare integration, error fix)
- PostgreSQL via Neon DB (psycopg2 connection pool)
- Mini App backend (FastAPI) for web dashboard
- Cloudflare deployment with per-user OAuth
- systemd services for bot and API server

### CLONE BOT
- Clone/staging variant with core modules
- 11 Python files (no API server, no Cloudflare, no error fix)
- Same PostgreSQL backend with isolated schema (`OXYGENT_SCHEMA=clone`)
- Uses shared config from MAIN BOT

## External API Endpoints

| Service | Base URL | Auth | Purpose |
|---------|----------|------|---------|
| OpenCode Zen | `https://opencode.ai/zen/v1` | None (free tier) | AI model inference |
| Telegram Bot API | `https://api.telegram.org` | Bot token | User interaction |
| PostgreSQL (Neon) | Connection string | DB credentials | Persistent storage |
| Cloudflare API | `https://api.cloudflare.com` | User OAuth tokens | Deployment |
| DuckDuckGo | `https://api.duckduckgo.com` | None | Web search |

## Key Design Patterns

1. **Agent Loop** — Hermes-style THINK→ACT→OBSERVE cycle with max 8 turns
2. **Model Rotation** — Failover across free-tier models with exponential backoff
3. **Sandboxed Execution** — Per-user/per-session filesystem isolation
4. **Dual Memory** — File-based (HermesMemory) + PostgreSQL (users table)
5. **Credit System** — Telegram Stars for paid usage, daily limits for free tier
6. **Per-User OAuth** — Each user connects their own Cloudflare account
7. **Schema Isolation** — Clone bot uses separate schema in same database
8. **Approval System** — Dangerous tools require user confirmation
9. **Connection Pooling** — 5-50 connections with automatic validation and recycling

## Related Codemaps

- [MODULES.md](MODULES.md) — Detailed module documentation
- [FILES.md](FILES.md) — Directory structure and file purposes
