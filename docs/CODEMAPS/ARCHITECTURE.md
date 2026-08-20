# System Architecture Codemap

**Last Updated:** 2026-08-20
**Entry Points:** `MAIN BOT/main.py`, `CLONE BOT/main.py`

## Overview

OXYGENT is a Telegram bot that provides AI-powered coding assistance with a Hermes-style agent loop, sandboxed code execution, memory systems, and a credit-based payment model.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram User                        │
│              (commands, callbacks, messages)            │
└──────────────────────┬──────────────────────────────────┘
                       │ python-telegram-bot (Async)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     main.py                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Handlers │ │Payments  │ │ Commands │ │ Callbacks │  │
│  │          │ │ Handlers │ │          │ │           │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │             │            │              │        │
│       ▼             ▼            ▼              ▼        │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Configuration Layer                │   │
│  │              (config.py)                        │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌───────────┐ ┌──────────────┐
│ agent_engine │ │ payments  │ │ memory_system│
│              │ │           │ │              │
│ • Agent Loop │ │ • Stars   │ │ • File Mem   │
│ • Model Rot  │ │ • Credits │ │ • SQLite DB  │
│ • Sandboxed  │ │ • Docs    │ │              │
│   Execution  │ │           │ │              │
└──────┬───────┘ └─────┬─────┘ └──────┬───────┘
       │               │              │
       ▼               ▼              ▼
┌──────────────┐ ┌───────────┐ ┌──────────────┐
│coding_tools  │ │ database  │ │              │
│              │ │           │ │              │
│ • read_file  │ │ • Users   │ │              │
│ • write_file │ │ • Sessions│ │              │
│ • search     │ │ • Payments│ │              │
│ • patch      │ │ • Channels│ │              │
│ • terminal   │ │ • Creds   │ │              │
│ • exec_code  │ │ • Pool    │ │              │
│ • web_search │ │           │ │              │
└──────────────┘ └───────────┘ └──────────────┘
       │               │              │
       ▼               ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                   External Services                     │
│  ┌────────────┐ ┌────────────┐ ┌─────────────────────┐ │
│  │ OpenCode   │ │ PostgreSQL │ │ Telegram Bot API    │ │
│  │ Zen API    │ │ (Neon DB)  │ │                     │ │
│  │            │ │            │ │                     │ │
│  │ opus-lite  │ │ Supabase   │ │ Polling / Webhook   │ │
│  │ nemotron   │ │            │ │                     │ │
│  │ qwen3-coder│ │            │ │                     │ │
│  └────────────┘ └────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. User Message Flow
```
User sends message → main.py handlers → extract user info
  → database.get_user(user_id) → Check credit balance
    → If free: show upgrade prompt
    → If paid: agent_engine.process_message()
      → Select model from rotation
      → Load conversation context
      → Send to OpenCode Zen API
      → Execute tools in sandbox
      → Return response to user
```

### 2. Agent Loop Flow (agent_engine.py)
```
process_message()
  → Create tool sandbox
  → Build system prompt with tools
  → Send to model endpoint
  → Parse response for tool calls
  → Execute tool → Feed result back
  → Repeat until: answer provided / max iterations / credit limit
  → Save context to memory
  → Deduct credits
  → Return final answer
```

### 3. Payment Flow (payments.py)
```
User clicks "Buy Credits" → Show packages
  → Generate Telegram Stars invoice
  → User pays → pre_checkout_query handler
  → successful_payment handler → Save to database
  → Grant credits → Confirm to user
```

### 4. Memory Flow (memory_system.py)
```
After each conversation:
  → HermesMemory.save_conversation()
    → Write to file system (./memory/)
  → MemoryDatabase.save_context()
    → Write to SQLite (./data/memory.db)
    → Extract keywords, store metadata
```

## Component Relationships

| Component | Depends On | Role |
|-----------|-----------|------|
| `main.py` | All modules | Entry point, routing, orchestration |
| `config.py` | (none) | Environment, models, messages, limits |
| `database.py` | `config.py` | PostgreSQL CRUD, connection pooling |
| `agent_engine.py` | `coding_tools`, `config` | AI agent loop, model rotation |
| `coding_tools.py` | (none) | 7-tool sandbox implementation |
| `payments.py` | `database.py` | Telegram Stars payments, credit management |
| `memory_system.py` | (none) | Dual-layer memory (file + SQLite) |

## Two Deployments

### MAIN BOT
- Full production deployment
- All 7 modules active
- PostgreSQL via Supabase/Neon
- Memory: File + SQLite dual layer

### CLONE BOT
- Clone/staging variant
- Same core modules + 2 extras:
  - `context_engine.py` — Token tracking, auto-compaction
  - `tools.py` — Alternate memory system (SQLite-only)
- Uses `config.from_main_bot = True` (shares config with MAIN BOT)

## External API Endpoints

| Service | Base URL | Auth | Purpose |
|---------|----------|------|---------|
| OpenCode Zen | `https://opencode.ai/zen/v1` | None (free tier) | AI model inference |
| Telegram Bot API | `https://api.telegram.org` | Bot token | User interaction |
| PostgreSQL (Neon) | Connection string | DB credentials | Persistent storage |

## Key Design Patterns

1. **Agent Loop** — Hermes-style THINK→ACT→OBSERVE cycle
2. **Model Rotation** — Failover across multiple free-tier models
3. **Sandboxed Execution** — All tool outputs contained within memory
4. **Dual Memory** — File-based (HermesMemory) + SQLite (MemoryDatabase)
5. **Credit System** — Telegram Stars for paid usage, free tier limited
6. **Rate Limiting** — Per-user cooldowns, message length limits

## Related Codemaps

- [MODULES.md](MODULES.md) — Detailed module documentation
- [FILES.md](FILES.md) — Directory structure and file purposes
