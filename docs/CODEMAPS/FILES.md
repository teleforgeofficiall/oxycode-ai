# Files Codemap

**Last Updated:** 2026-08-20

## Project Root

```
C:\Users\Teleforge\Desktop\OXYCODE AI BOT\
├── ARCHITECTURE.md          # High-level system architecture
├── README.md                # Project overview and setup
├── DOCS_UPDATE_LOG.md       # Documentation changelog
├── CLAUDE.md                # Claude Code configuration
├── .gitignore               # Git ignore rules
│
├── MAIN BOT/                # Production bot deployment
├── CLONE BOT/               # Clone/staging variant
├── archive/                 # Archived VPS deployment scripts
├── docs/                    # Documentation (codemaps)
└── .opencode/               # OpenCode configuration
```

---

## MAIN BOT/

Production deployment of OXYGENT Telegram bot.

| File | Lines | Purpose | Key Exports |
|------|-------|---------|-------------|
| `main.py` | 1265+ | Entry point, handlers, orchestration | Telegram bot setup, all command/callback handlers |
| `config.py` | ~150 | Environment variables, model configs, messages | `TELEGRAM_TOKEN`, `AI_MODELS`, `MESSAGES`, `CREDIT_PACKAGES` |
| `database.py` | ~200 | PostgreSQL async operations, connection pooling | `Database` class, `db` singleton |
| `agent_engine.py` | ~300 | Hermes-style AI agent loop | `AgentEngine` class, `agent_engine` singleton |
| `coding_tools.py` | ~250 | 7-tool sandbox for code/file operations | `CodingTools` class, `coding_tools` singleton |
| `payments.py` | ~150 | Telegram Stars payment processing | `Payments` class, `payments` singleton |
| `memory_system.py` | ~150 | Dual-layer memory (file + SQLite) | `HermesMemory`, `MemoryDatabase`, `memory_db` |
| `requirements.txt` | ~20 | Python dependencies | `python-telegram-bot>=20.0`, `asyncpg`, `aiohttp` |

### main.py — Handler Structure

```
main.py
├── Imports (all modules)
├── Telegram Application setup
├── Command Handlers
│   ├── /start — Welcome, create user, show menu
│   ├── /help — Usage instructions
│   ├── /buy — Show credit packages
│   ├── /balance — Check remaining credits
│   ├── /memory — View/manage conversation history
│   ├── /reset — Clear conversation context
│   ├── /model — Switch AI model (if allowed)
│   └── /channels — Manage linked Telegram channels
├── Callback Query Handlers
│   ├── buy_package_* — Package selection callbacks
│   ├── confirm_purchase — Purchase confirmation
│   ├── channel_* — Channel management callbacks
│   └── memory_* — Memory management callbacks
├── Message Handlers
│   ├── Text messages → agent_engine.process_message()
│   ├── Pre-checkout queries → payments.handle_pre_checkout()
│   └── Successful payments → payments.handle_successful_payment()
├── Error Handler
│   └── Global exception catching and logging
└── Main
    └── Application.run_polling()
```

---

## CLONE BOT/

Clone/staging variant with 2 additional modules.

| File | Lines | Purpose | Differences from MAIN |
|------|-------|---------|----------------------|
| `main.py` | ~1200 | Same structure as MAIN BOT | Uses `config.from_main_bot = True` |
| `config.py` | ~160 | Configuration with clone flag | Has `from_main_bot = True` to share MAIN config |
| `database.py` | ~200 | Same PostgreSQL operations | Identical to MAIN |
| `agent_engine.py` | ~300 | Same agent loop | Identical to MAIN |
| `coding_tools.py` | ~250 | Same 7 tools | Identical to MAIN |
| `payments.py` | ~150 | Same payment system | Identical to MAIN |
| `memory_system.py` | ~150 | Same dual memory | Identical to MAIN |
| **`context_engine.py`** | ~120 | **Token tracking, auto-compaction** | **CLONE BOT only** |
| **`tools.py`** | ~100 | **Alternate SQLite memory system** | **CLONE BOT only** |
| `requirements.txt` | ~20 | Same dependencies | Identical to MAIN |

### CLONE BOT Unique Files

#### context_engine.py
```
Purpose: Monitor token usage and auto-compact long conversations
Class: ContextEngine
Methods:
  - track_tokens(messages) → int
  - should_compact(messages) → bool
  - compact(messages) → list[dict]
  - get_token_usage(user_id) → dict
Strategy:
  - Count tokens in message list
  - When exceeding threshold, summarize older messages
  - Keep recent N messages in full
```

#### tools.py
```
Purpose: SQLite-only memory system (no file-based storage)
Class: MemorySystem
Methods:
  - save(user_id, key, value) → None
  - get(user_id, key) → str or None
  - search(user_id, query) → list[dict]
  - delete(user_id, key) → None
Storage: SQLite database (./data/tools.db)
```

---

## archive/

VPS deployment and management scripts (not actively used).

| File | Purpose |
|------|---------|
| `check_vps.py` | Check VPS connection status |
| `deploy_clone_vps.py` | Deploy clone bot to VPS |
| `deploy_vps.py` | Deploy main bot to VPS |
| `monitor_vps.py` | Monitor VPS health/metrics |
| `test_vps_connection.py` | Test VPS SSH connectivity |
| `start_services.sh` | Start bot services on VPS |
| `stop_services.sh` | Stop bot services on VPS |
| `setup_vps.sh` | Initial VPS setup script |

---

## docs/

Documentation directory.

```
docs/
└── CODEMAPS/
    ├── ARCHITECTURE.md    # System overview, data flow
    ├── MODULES.md         # Module docs, APIs, dependencies
    └── FILES.md           # This file
```

---

## Data Directories (Runtime)

Created at runtime, not in git.

| Path | Purpose | Format |
|------|---------|--------|
| `./memory/` | HermesMemory file storage | `{telegram_id}.json` |
| `./data/` | SQLite databases | `memory.db`, `tools.db` |
| `./.agent/` | Agent working state | Various |
| `./logs/` | Application logs | `.log` files |

---

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `CLAUDE.md` | Project root | Claude Code session instructions |
| `.gitignore` | Project root | Git ignore rules |
| `.opencode/` | Project root | OpenCode IDE configuration |
| `requirements.txt` | Each bot | Python package dependencies |

---

## Key File Locations Summary

| What | Where |
|------|-------|
| Entry point | `MAIN BOT/main.py`, `CLONE BOT/main.py` |
| All config | `*/config.py` |
| Database layer | `*/database.py` |
| AI agent loop | `*/agent_engine.py` |
| Tool sandbox | `*/coding_tools.py` |
| Payment system | `*/payments.py` |
| Memory (file) | `*/memory_system.py` → `./memory/` |
| Memory (SQLite) | `*/memory_system.py` → `./data/memory.db` |
| Token tracking | `CLONE BOT/context_engine.py` |
| Alternate memory | `CLONE BOT/tools.py` |
| VPS scripts | `archive/` |
| Documentation | `docs/CODEMAPS/` |

---

## Related Codemaps

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview and data flow
- [MODULES.md](MODULES.md) — Detailed module documentation
