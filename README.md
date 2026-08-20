# OXYGENT - AI Coding Assistant Bot

> An autonomous AI coding agent built as a Telegram bot by **OXYCODE TEAM**

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4)
![Database](https://img.shields.io/badge/PostgreSQL-Neon%20DB-336791)

---

## Overview

OXYGENT is a Telegram bot that acts as an autonomous AI coding agent. It can:

- **Write code** in any programming language
- **Debug errors** and fix broken code
- **Build websites, bots & apps** from natural language descriptions
- **Explain code** in plain English
- **Voice replies** with text-to-speech
- **Web search** for documentation and examples
- **Generate UI/HTML** from text descriptions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Bot API                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  • Command handlers (/start, /help, /voice, /status, etc.) │
│  • Callback routing (menus, payments, sessions)             │
│  • AI response orchestration                                │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  agent_engine.py │  │  coding_tools.py │  │  memory_system.py │
│  Hermes-style    │  │  7-tool sandbox  │  │  Per-user memory  │
│  agent loop      │  │  File ops, web   │  │  Auto-detect info │
│  Tool calling    │  │  search, terminal│  │  File + DB hybrid │
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                      database.py                            │
│  PostgreSQL (Neon DB) — Users, Sessions, Payments, Channels │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    config.py                                │
│  BOT_TOKEN, ADMIN_IDS, AI models, Database URL              │
└─────────────────────────────────────────────────────────────┘
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
   
   Create a `.env` file in `MAIN BOT/` directory:
   ```env
   # Telegram Bot Token (from @BotFather)
   BOT_TOKEN=your_bot_token_here
   
   # Admin User IDs (comma-separated)
   ADMIN_IDS=123456789,987654321
   
   # PostgreSQL Database URL (Neon DB)
   DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
   
   # AI Model Configuration (optional - defaults work out of the box)
   OPENCODE_ZEN_MODEL=hy3-free
   OPENCODE_ZEN_FALLBACKS=nemotron-3.5-lightning-free,nemotron-3-ultra-free,laguna-s-2.1-free
   ```

4. **Initialize database**
   
   The database tables are created automatically on first run. Ensure your PostgreSQL database is accessible.

5. **Run the bot**
   ```bash
   cd "MAIN BOT"
   python main.py
   ```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `ADMIN_IDS` | Yes | Comma-separated admin user IDs |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENCODE_ZEN_MODEL` | No | Primary AI model (default: `hy3-free`) |
| `OPENCODE_ZEN_FALLBACKS` | No | Comma-separated fallback models |
| `OXYGENT_SCHEMA` | No | Database schema for staging/clone bots |

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `daily_limit` | 20 | Free messages per user per day |
| `referral_bonus` | 20 | Credits earned per successful referral |
| `max_sessions` | 5 | Maximum code sessions per user |

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

---

## AI Models

OXYGENT uses OpenCode Zen API with automatic model rotation for rate-limit immunity.

### Primary Model
- `hy3-free` - Default model

### Fallback Models (in order)
1. `nemotron-3.5-lightning-free`
2. `nemotron-3-ultra-free`
3. `laguna-s-2.1-free`

The system automatically rotates through models on rate limits (429) or server errors (5xx).

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
4. Run with a process manager:
   ```bash
   # Using systemd
   sudo systemctl enable oxygent-bot
   sudo systemctl start oxygent-bot
   
   # Using pm2
   pm2 start main.py --name oxygent-bot
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

---

## CLONE BOT

The `CLONE BOT/` directory contains an enhanced variant designed for staging or multi-instance deployments. Key differences:

| Feature | Main Bot | Clone Bot |
|---------|----------|-----------|
| Primary Model | `hy3-free` | `mimo-v2.5-free` |
| Fallback Models | 3 models | 5 models (includes `deepseek-v4-flash-free`) |
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

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `DATABASE_URL is missing or not a Postgres URL` | Set valid PostgreSQL URL in `.env` |
| `connection pool exhausted` | Increase pool size or check for connection leaks |
| Bot not responding | Check `BOT_TOKEN` is valid and bot is started |
| AI unavailable messages | Free tier rate limit — wait 30 seconds |
| Voice not working | Ensure `edge-tts` is installed: `pip install edge-tts`

### Logs

Check logs for detailed error information. The bot uses Python's `logging` module with configurable levels.

---

## License

Proprietary — OXYCODE TEAM

---

## Support

For issues and feature requests, contact the OXYCODE TEAM.
