# OXYGENT Clone Bot

> Staging/variant deployment of the OXYGENT AI Coding Assistant

---

## Overview

The Clone Bot is a variant of the main OXYGENT bot designed for:

- **Staging environments** — Test changes before production
- **Multi-instance deployments** — Run alongside the main bot
- **Isolated testing** — Separate database schema prevents data contamination

---

## Key Differences from Main Bot

| Feature | Main Bot | Clone Bot |
|---------|----------|-----------|
| Primary AI Model | `hy3-free` | `mimo-v2.5-free` |
| Fallback Models | 3 models | 5 models (includes `deepseek-v4-flash-free`) |
| Tool Set | 7 sandbox tools | 12 tools (includes GitHub, screenshots, API testing) |
| Context Engine | — | Token tracking + auto-compaction |
| Extra Dependencies | — | `asyncpg`, `aiofiles` |
| Database Schema | `public` | Configurable via `OXYGENT_SCHEMA` |
| Production Use | Yes | Staging/Testing |
| Data Isolation | Shared | Schema-isolated |

---

## Setup

### 1. Configure Environment

Create `.env` in `CLONE BOT/` directory:

```env
# Telegram Bot Token (different from main bot)
BOT_TOKEN=your_clone_bot_token

# Admin User IDs
ADMIN_IDS=123456789

# PostgreSQL Database URL (can use same DB as main)
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require

# CRITICAL: Set isolated schema for clone
OXYGENT_SCHEMA=clone

# AI Model (defaults to mimo-v2.5-free, different from main bot)
OPENCODE_ZEN_MODEL=mimo-v2.5-free
OPENCODE_ZEN_FALLBACKS=deepseek-v4-flash-free,hy3-free,nemotron-3.5-lightning-free,nemotron-3-ultra-free,laguna-s-2.1-free
```

### 2. Database Schema Isolation

The `OXYGENT_SCHEMA` environment variable tells the bot to use a separate PostgreSQL schema:

```sql
-- Automatically created on first run
CREATE SCHEMA IF NOT EXISTS clone;
SET search_path TO clone;
```

This ensures:
- Clone bot tables don't interfere with main bot
- Same PostgreSQL database can serve both bots
- Easy cleanup (just drop the schema)

### 3. Run the Clone

```bash
cd "CLONE BOT"
python main.py
```

---

## Architecture

The Clone Bot uses the same architecture as the Main Bot:

```
┌─────────────────────────────────────────────────┐
│              Clone Bot (OXYGENT)                │
├─────────────────────────────────────────────────┤
│  main.py          — Command handlers            │
│  agent_engine.py  — Hermes-style agent loop     │
│  coding_tools.py  — 7-tool sandbox             │
│  memory_system.py — Per-user memory            │
│  database.py      — PostgreSQL (schema-isolated)│
│  config.py        — Configuration               │
│  payments.py      — Telegram Stars              │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│         PostgreSQL (Neon DB)                    │
│  Schema: clone                                  │
│  Tables: users, channels, sessions, etc.        │
└─────────────────────────────────────────────────┘
```

---

## Additional Files

The Clone Bot includes extra files not in the Main Bot:

| File | Purpose |
|------|---------|
| `context_engine.py` | Token tracking, auto-compaction at 80% capacity, conversation history management |
| `tools.py` | 12-tool registry (file ops, web, GitHub, code analysis, screenshots, API testing) |

### Context Engine

The `context_engine.py` provides conversation context management:

- **Token Tracking**: Estimates token usage (1 token ≈ 4 chars)
- **Auto-Compaction**: Triggers at 80% of `MAX_CONTEXT_TOKENS` (4000)
- **History Management**: Maintains ordered conversation history with timestamps
- **System Prompt Optimization**: Caps system prompt at 3000 chars

### Tools Registry

The `tools.py` registers 12 tools callable by the agent:

```python
TOOLS = {
    "website_screenshot",  # Playwright-based screenshots
    "web_search",          # DuckDuckGo search
    "code_execute",        # Subprocess code execution
    "file_create",         # File creation
    "file_read",           # File reading
    "github_push",         # GitHub API push
    "explain_code",        # Line-by-line code explanation
    "debug_code",          # Automated debugging
    "optimize_code",       # Code optimization suggestions
    "convert_code",        # Language conversion
    "write_tests",         # Test generation
    "api_test",            # HTTP API testing
}
```

---

## Use Cases

### 1. Staging Environment

Run the clone alongside production to test new features:

```bash
# Main bot (production)
cd "MAIN BOT"
BOT_TOKEN=prod_token DATABASE_URL=... python main.py

# Clone bot (staging)
cd "CLONE BOT"
BOT_TOKEN=staging_token DATABASE_URL=... OXYGENT_SCHEMA=staging python main.py
```

### 2. Multi-Tenant Deployment

Run multiple instances for different user groups:

```bash
# Instance 1
OXYGENT_SCHEMA=tenant_a python main.py

# Instance 2
OXYGENT_SCHEMA=tenant_b python main.py
```

### 3. Testing & Development

Isolated environment for development without affecting production data:

```bash
OXYGENT_SCHEMA=dev python main.py
```

---

## Database Migration

To clean up a clone's data:

```sql
-- Drop the clone schema and all its tables
DROP SCHEMA clone CASCADE;
```

To reset:

```sql
-- Drop and recreate
DROP SCHEMA clone CASCADE;
CREATE SCHEMA clone;
```

The bot will automatically recreate tables on next startup.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tables not found | Ensure `OXYGENT_SCHEMA` is set in `.env` |
| Schema conflict | Check schema name doesn't conflict with PostgreSQL system schemas |
| Connection errors | Verify `DATABASE_URL` points to accessible database |

---

## License

Proprietary — OXYCODE TEAM
