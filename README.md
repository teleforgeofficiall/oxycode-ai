# OXYGENT - AI Coding Assistant Bot

> An autonomous AI coding agent built as a Telegram bot + Mini App by **OXYCODE TEAM**

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4)
![Database](https://img.shields.io/badge/PostgreSQL-Neon%20DB-336791)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688)
![Cloudflare](https://img.shields.io/badge/Cloudflare-F48120-F48120)

---

## Overview

OXYGENT is a Telegram bot + Mini App platform that acts as an autonomous AI coding agent. It can:

- **Write code** in any programming language
- **Debug errors** and fix broken code
- **Build websites, bots & apps** from natural language descriptions
- **Deploy to Cloudflare** (Pages & Workers) with per-user OAuth
- **Auto-fix deployed sites** using AI error analysis
- **Explain code** in plain English
- **Voice replies** with text-to-speech
- **Web search** for documentation and examples
- **Generate UI/HTML** from text descriptions

---

## Architecture

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

---

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **AI Chat** | Conversational coding assistance via OpenCode Zen API |
| **Code Sessions** | Persistent sessions for multi-file projects |
| **Hermes Agent** | Tool-use agent loop for autonomous code building |
| **Voice Replies** | Text-to-speech via Edge TTS (male/female) |
| **Web Search** | DuckDuckGo integration for documentation lookup |
| **Code Explanation** | `/explain` command for line-by-line code analysis |
| **Code Fixing** | `/fix` command for debugging broken code |
| **UI Generation** | `/ui` command to generate HTML/CSS/JS from descriptions |

### Mini App Features

| Feature | Description |
|---------|-------------|
| **Web Dashboard** | FastAPI backend with JWT authentication |
| **Project Management** | Create, view, and delete projects |
| **AI Chat Proxy** | Send messages to AI directly from the browser |
| **Cloudflare Deploy** | Deploy projects to Pages or Workers |
| **Auto-Fix** | AI-powered error detection and repair |
| **Project Analyzer** | Auto-detect project type and tech stack |

### User Features

| Feature | Description |
|---------|-------------|
| **Referral System** | Earn bonus credits by inviting friends |
| **Telegram Stars** | Buy extra credits via Telegram's payment system |
| **Daily Limits** | Free tier with configurable daily message limit |
| **Force-Join Channels** | Require users to join channels before using bot |
| **Memory System** | Bot remembers user preferences and context |

### Admin Features

| Feature | Description |
|---------|-------------|
| **Admin Panel** | `/admin` command for bot management |
| **Broadcast** | Send messages to all users |
| **User Management** | Ban/unban users |
| **Channel Management** | Add/remove force-join channels |
| **Statistics** | User count, payments, referrals, sessions |
| **Maintenance Mode** | Toggle maintenance mode (admin-only access) |

---

## Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Start bot & check channel membership |
| `/menu` | Open main menu |
| `/help` | Show help message |
| `/status` | View your info, limits & credits |
| `/create` | Create/manage code sessions |
| `/voice` | Toggle voice replies or speak text |
| `/voicegender` | Set voice to male/female |
| `/background <question>` | Ask quick question during a task |
| `/search <query>` | Web search via DuckDuckGo |
| `/explain` | Explain pasted code |
| `/fix` | Debug broken code |
| `/ui` | Generate UI from text description |
| `/memory` | View stored memory |
| `/forget` | Clear your memory |
| `/cancel` | Cancel current operation |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Open admin panel |
| `/selftest` | Run health self-test |

---

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL database (Neon DB recommended)
- Telegram Bot Token (from @BotFather)
- OpenCode Zen API access (free tier available)
- Cloudflare account (optional, for deployment features)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-repo/oxygent-bot.git
   cd oxygent-bot
   ```

2. **Install dependencies**
   ```bash
   # For the Main Bot
   cd "MAIN BOT"
   pip install -r requirements.txt
   
   # For the Clone Bot (includes extra async deps)
   cd "CLONE BOT"
   pip install -r requirements.txt
   ```

3. **Configure environment**
   
   Copy `.env.example` to `.env` and fill in the values:
   ```bash
   cp .env.example .env
   ```
   
   Required variables:
   ```env
   # Telegram Bot Token (from @BotFather)
   BOT_TOKEN=your_bot_token_here
   
   # Admin User IDs (comma-separated)
   ADMIN_IDS=123456789,987654321
   
   # PostgreSQL Database URL (Neon DB)
   DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
   
   # JWT Secret for Mini App auth (generate a random string)
   JWT_SECRET=your-random-secret-here
   
   # AI Model Configuration (optional - defaults work out of the box)
   OPENCODE_ZEN_MODEL=mimo-v2.5-free
   OPENCODE_ZEN_FALLBACKS=deepseek-v4-flash-free,hy3-free,nemotron-3.5-lightning-free,nemotron-3-ultra-free,laguna-s-2.1-free
   
   # Maintenance Mode (true/false)
   MAINTENANCE_MODE=false
   
   # Cloudflare OAuth (optional, for deployment features)
   CLOUDFLARE_CLIENT_ID=your_client_id
   CLOUDFLARE_CLIENT_SECRET=your_client_secret
   CLOUDFLARE_REDIRECT_URI=https://your-domain.com/cloudflare-callback
   ```

4. **Initialize database**
   
   The database tables are created automatically on first run. Ensure your PostgreSQL database is accessible.

5. **Run the bot**
   ```bash
   cd "MAIN BOT"
   python main.py
   ```

6. **Run the API server** (optional, for Mini App)
   ```bash
   cd "MAIN BOT"
   uvicorn api_server:app --host 0.0.0.0 --port 8000
   ```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `ADMIN_IDS` | Yes | Comma-separated admin user IDs |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | Secret key for JWT authentication (Mini App) |
| `OPENCODE_ZEN_MODEL` | No | Primary AI model (default: `mimo-v2.5-free`) |
| `OPENCODE_ZEN_FALLBACKS` | No | Comma-separated fallback models |
| `OXYGENT_SCHEMA` | No | Database schema for staging/clone bots |
| `MAINTENANCE_MODE` | No | Enable maintenance mode (`true`/`false`) |
| `CLOUDFLARE_CLIENT_ID` | No | Cloudflare OAuth app client ID |
| `CLOUDFLARE_CLIENT_SECRET` | No | Cloudflare OAuth app client secret |
| `CLOUDFLARE_REDIRECT_URI` | No | Cloudflare OAuth callback URL |

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `daily_limit` | 20 | Free messages per user per day |
| `referral_bonus` | 20 | Credits earned per successful referral |
| `max_sessions` | 5 | Maximum code sessions per user |
| `global_max_sites` | 5 | Maximum Cloudflare Pages sites per user |
| `global_max_workers` | 5 | Maximum Cloudflare Workers per user |

---

## Database Schema

### Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts, settings, and limits |
| `channels` | Force-join Telegram channels |
| `user_states` | Conversation flow states |
| `code_sessions` | Code creation sessions |
| `payments` | Telegram Stars transactions |
| `broadcasts` | Broadcast message log |
| `settings` | Admin-configurable settings |
| `workers` | Cloudflare Worker hosting info |
| `deployments` | Deployed projects (Vercel/Cloudflare) |
| `projects` | Mini App projects |
| `daily_messages` | Daily message tracking for Mini App |
| `cloudflare_accounts` | Per-user Cloudflare OAuth tokens |

### Key User Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | BIGINT | Telegram user ID (primary key) |
| `bonus_messages` | INTEGER | Purchased/referred credit balance |
| `msg_count` | INTEGER | Today's message count |
| `msg_date` | TEXT | Date of last message (for daily reset) |
| `voice_enabled` | INTEGER | Voice replies toggle |
| `voice_gender` | TEXT | Voice gender (male/female) |
| `referral_code` | TEXT | Unique referral code |
| `referred_by` | BIGINT | Referrer's user ID |

---

## AI Models

OXYGENT uses OpenCode Zen API with automatic model rotation for rate-limit immunity.

### Primary Model
- `mimo-v2.5-free` - Default model

### Fallback Models (in order)
1. `deepseek-v4-flash-free`
2. `hy3-free`
3. `nemotron-3.5-lightning-free`
4. `nemotron-3-ultra-free`
5. `laguna-s-2.1-free`

The system automatically rotates through models on rate limits (429) or server errors (5xx).

---

## Mini App (Web Dashboard)

The Mini App provides a web-based interface for managing projects and deploying to Cloudflare.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/telegram` | Verify Telegram initData, return JWT |
| GET | `/api/user/me` | Get current user profile |
| GET | `/api/projects` | List user's projects |
| POST | `/api/projects` | Create new project |
| GET | `/api/projects/:id` | Get project details |
| DELETE | `/api/projects/:id` | Delete project |
| POST | `/api/chat` | Send message to AI, get response |
| GET | `/api/limits` | Get user's daily limits |
| POST | `/api/deploy` | Deploy to Cloudflare |
| POST | `/api/fix` | AI error analysis |
| POST | `/api/fix/apply` | Apply fixes and redeploy |
| GET | `/api/cloudflare/status` | Check Cloudflare connection |
| GET | `/api/cloudflare/auth-url` | Get OAuth authorization URL |
| GET | `/api/cloudflare/callback` | Handle OAuth callback |
| DELETE | `/api/cloudflare/disconnect` | Disconnect Cloudflare account |

### Authentication Flow

1. User opens Mini App in Telegram
2. Frontend sends `initData` to `/api/auth/telegram`
3. Backend verifies HMAC signature with `BOT_TOKEN`
4. Backend generates JWT (7-day expiry)
5. Frontend stores JWT and uses it for all subsequent requests

---

## Cloudflare Deployment

OXYGENT supports deploying user projects to Cloudflare Pages and Workers using per-user OAuth.

### Deployment Flow

1. User connects their Cloudflare account via OAuth
2. User builds a project (website, bot, etc.)
3. User clicks "Deploy" in Mini App
4. Backend uploads files to Cloudflare Pages or Workers
5. Backend returns live URL

### Supported Deployment Targets

| Target | Use Case | URL Format |
|--------|----------|------------|
| **Cloudflare Pages** | Static websites, SPAs | `https://{project}.pages.dev` |
| **Cloudflare Workers** | Telegram bots, APIs | `https://{name}.{subdomain}.workers.dev` |

### Required Cloudflare Scopes

- Workers Scripts: Edit
- Workers KV Storage: Edit
- Workers R2 Storage: Edit
- Cloudflare Pages: Edit
- Zone Settings: Read
- DNS: Read/Write

---

## Error Fix System

OXYGENT includes an AI-powered error detection and auto-repair system for deployed projects.

### Flow

1. User clicks "Fix" button in Mini App
2. Frontend sends error context (URL, error message, stack trace)
3. Backend sends error + project code to OpenCode AI
4. AI analyzes the error and suggests a fix
5. If auto-fixable, backend re-deploys to Cloudflare
6. Frontend receives fix result

### Error Types Handled

- HTTP errors (404, 500, CORS)
- JavaScript runtime errors
- Build/compilation errors
- Missing resources
- Deployment failures

---

## Agent System

### Hermes-Style Agent Loop

The agent engine follows the architecture from NousResearch/hermes-agent:

```
THINK → model returns tool_calls → execute tool in sandbox →
feed result back as role:"tool" → repeat until finish_reason=="stop"
or MAX_TURNS reached
```

### Available Tools

| Tool | Description |
|------|-------------|
| `write_file` | Create files in the sandbox |
| `read_file` | Read existing files |
| `patch_file` | Edit files via find/replace |
| `search_files` | Search by name or content |
| `terminal` | Run sandboxed shell commands |
| `execute_code` | Execute Python/JavaScript snippets |
| `web_search` | Search DuckDuckGo |

### Approval System

Dangerous tools (`write_file`, `patch_file`, `terminal`, `execute_code`) require user approval before execution. The agent pauses, shows approval buttons, and resumes after user confirms.

### Sandbox

Each user gets an isolated sandbox at `/tmp/oxygent_sandbox/<uid>/<sid>/`. Files are created and modified within this sandbox, preventing cross-user contamination.

---

## Payment System

### Telegram Stars

Users can purchase extra credits via Telegram Stars (XTR currency).

| Stars | Credits | Label |
|-------|---------|-------|
| 3 | 10 | Starter |
| 10 | 35 | Basic |
| 30 | 120 | Pro |
| 100 | 400 | Premium |
| 300 | 1500 | Ultimate |

### Credit System

- **Free Tier**: 20 messages/day (configurable)
- **Bonus Credits**: Purchased via Stars or earned via referrals
- **Usage**: Free messages consumed first, then bonus credits

---

## Deployment

### VPS Deployment

1. Upload project to VPS
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` with production values
4. Run with systemd services:

```bash
# Bot service
sudo systemctl enable oxycode-bot
sudo systemctl start oxycode-bot

# API server
sudo systemctl enable oxycode-api
sudo systemctl start oxycode-api
```

Or use the deployment script:
```bash
cd "MAIN BOT"
python deploy_vps.py
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Systemd Services

The bot runs as two systemd services:

| Service | Command | Port |
|---------|---------|------|
| `oxycode-bot` | `python main.py` | None (polling) |
| `oxycode-api` | `uvicorn api_server:app --host 0.0.0.0 --port 8000` | 8000 |

Check status:
```bash
systemctl status oxycode-bot
systemctl status oxycode-api
```

---

## CLONE BOT

The `CLONE BOT/` directory contains an enhanced variant designed for staging or multi-instance deployments. Key differences:

| Feature | Main Bot | Clone Bot |
|---------|----------|-----------|
| Primary Model | `mimo-v2.5-free` | `mimo-v2.5-free` |
| Fallback Models | 5 models | 5 models (same) |
| Database Schema | `public` | Configurable via `OXYGENT_SCHEMA` |
| Tool Set | 7 sandbox tools | 12 tools (includes GitHub, API testing, screenshots) |
| Extra Dependencies | — | `asyncpg`, `aiofiles` |
| Context Engine | — | Token tracking + auto-compaction |
| Use Case | Production | Staging / testing / multi-tenant |

### Clone Bot Extra Tools

The Clone Bot includes tools beyond the main bot's 7-tool sandbox:

| Tool | Description |
|------|-------------|
| `website_screenshot` | Capture screenshots of live websites (requires Playwright) |
| `github_push` | Push code to GitHub repositories |
| `explain_code` | Line-by-line code explanation |
| `debug_code` | Automated bug detection and fix suggestions |
| `optimize_code` | Code performance analysis and suggestions |
| `convert_code` | Convert code between programming languages |
| `write_tests` | Generate unit test scaffolding |
| `api_test` | Test HTTP API endpoints |
| `code_execute` | Execute code in a subprocess sandbox |

### Clone Bot Dependencies

The Clone Bot requires additional packages not in the Main Bot:

```txt
asyncpg>=0.29.0    # Async PostgreSQL driver
aiofiles>=23.0     # Async file I/O
```

Install with: `pip install -r requirements.txt` (includes both Main and Clone deps)

---

## Project Structure

```
OXYCODE AI BOT/
├── README.md                    # This file
├── .gitignore                   # Git ignore rules
│
├── MAIN BOT/                    # Production bot
│   ├── main.py                  # Telegram bot entry point
│   ├── config.py                # Configuration
│   ├── database.py              # PostgreSQL operations
│   ├── agent_engine.py          # AI agent loop
│   ├── coding_tools.py          # 7-tool sandbox
│   ├── payments.py              # Telegram Stars payments
│   ├── memory_system.py         # Triple-layer memory
│   ├── context_engine.py        # Token tracking
│   ├── api_server.py            # FastAPI Mini App backend
│   ├── cloudflare_oauth.py      # Per-user CF OAuth
│   ├── cloudflare_deploy.py     # CF Pages/Workers deployment
│   ├── error_fix.py             # AI error detection/repair
│   ├── project_analyzer.py      # Auto-detect project type
│   ├── deploy_vps.py            # SSH-based VPS deployment
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Example environment config
│   ├── SECURITY.md              # Security documentation
│   └── templates/               # HTML templates
│
├── CLONE BOT/                   # Clone/staging variant
│   └── (same structure as MAIN BOT)
│
├── docs/                        # Documentation
│   └── CODEMAPS/                # Architecture codemaps
│       ├── ARCHITECTURE.md      # System overview
│       ├── MODULES.md           # Module documentation
│       └── FILES.md             # File structure
│
└── vibesdk/                     # Cloudflare Workers SDK
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `DATABASE_URL is missing or not a Postgres URL` | Set valid PostgreSQL URL in `.env` |
| `connection pool exhausted` | Increase pool size or check for connection leaks |
| Bot not responding | Check `BOT_TOKEN` is valid and bot is started |
| AI unavailable messages | Free tier rate limit — wait 30 seconds |
| Voice not working | Ensure `edge-tts` is installed: `pip install edge-tts` |
| Mini App not loading | Ensure API server is running on port 8000 |
| JWT authentication failed | Check `JWT_SECRET` is set in `.env` |
| Cloudflare deploy fails | Verify `CLOUDFLARE_CLIENT_ID` and `CLOUDFLARE_CLIENT_SECRET` are set |
| Maintenance mode stuck | Use `/admin` to toggle maintenance mode off |

### Logs

Check logs for detailed error information. The bot uses Python's `logging` module with configurable levels.

```bash
# Check bot logs
journalctl -u oxycode-bot -f

# Check API logs
journalctl -u oxycode-api -f
```

---

## License

Proprietary — OXYCODE TEAM

---

## Support

For issues and feature requests, contact the OXYCODE TEAM.
