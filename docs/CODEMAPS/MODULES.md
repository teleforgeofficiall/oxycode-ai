# Modules Codemap

**Last Updated:** 2026-08-20

## Module Dependency Graph

```
                    config.py
                   /         \
          database.py     agent_engine.py
             |               /        \
         payments.py   coding_tools.py  memory_system.py
                         (standalone)     (standalone)
```

---

## 1. config.py

**Purpose:** Central configuration hub. Loads all environment variables, defines AI model endpoints, bot messages, and system limits.

**Location:** `MAIN BOT/config.py`, `CLONE BOT/config.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `TELEGRAM_TOKEN` | `str` | Telegram Bot API token |
| `AI_MODELS` | `list[dict]` | Available AI model configs (name, url, max_tokens) |
| `get_random_model()` | `function` | Returns random model from AI_MODELS |
| `CreditPackage` | `NamedTuple` | (id, stars, credits, label, description) |
| `CREDIT_PACKAGES` | `list[CreditPackage]` | Available purchase tiers |
| `MESSAGES` | `dict[str, str]` | All bot response templates |
| `RATE_LIMIT_SECONDS` | `int` | Cooldown between user requests (default: 30) |
| `MAX_MESSAGE_LENGTH` | `int` | Telegram message character limit |
| `AI_REQUEST_TIMEOUT` | `int` | HTTP timeout for AI API calls |
| `MAX_CONVERSATION_HISTORY` | `int` | Context window size |

**Dependencies:** `os`, `logging`

**Key Constants:**
- Models: `opus-lite`, `nemotron`, `qwen3-coder` (free tier, no API key)
- Limits: `MAX_FILE_SIZE = 10000`, `MAX_SEARCH_RESULTS = 5`, `MAX_PATCH_SIZE = 5000`
- Paths: `./memory/`, `./data/`, `./.agent/`

---

## 2. database.py

**Purpose:** PostgreSQL database layer using asyncpg. Handles all persistent storage operations for users, sessions, payments, and channels.

**Location:** `MAIN BOT/database.py`, `CLONE BOT/database.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `Database` | `class` | Main database interface with connection pool |
| `db` | `Database` | Module-level singleton instance |

**Database Class Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | `async` | Initialize connection pool, run migrations |
| `disconnect()` | `async` | Close pool |
| `get_user(telegram_id)` | `User or None` | Lookup user by Telegram ID |
| `create_user(telegram_id, username, first_name)` | `User` | Create new user record |
| `get_or_create_user(...)` | `User` | Atomic get-or-create |
| `update_user_credits(user_id, delta)` | `User` | Adjust credit balance |
| `get_free_tier_user(telegram_id)` | `User` | Create/return free-tier user |
| `save_session(user_id, messages, model_used)` | `ConversationSession` | Persist chat session |
| `get_active_session(user_id)` | `ConversationSession or None` | Get current session |
| `save_payment(user_id, package_id, amount, ...)` | `Payment` | Record payment |
| `save_channel(user_id, channel_link, channel_name)` | `Channel` | Save Telegram channel |
| `get_user_channels(user_id)` | `list[Channel]` | List user's channels |
| `update_channel_tokens(channel_id, tokens_used)` | `Channel` | Update token count |
| `get_channels_needing_repost()` | `list[Channel]` | Channels due for repost |

**Dependencies:** `asyncpg`, `config.py`

**Database Tables:**
- `users` — Telegram user profiles, credit balances, free_tier flag
- `conversation_sessions` — Chat history, model usage, timestamps
- `payments` — Transaction records (Telegram Stars)
- `channels` — Linked Telegram channels, token tracking

---

## 3. agent_engine.py

**Purpose:** Hermes-style AI agent loop. Orchestrates multi-turn conversations with tool calling, model rotation, and sandboxed execution.

**Location:** `MAIN BOT/agent_engine.py`, `CLONE BOT/agent_engine.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `AgentEngine` | `class` | Main agent orchestrator |
| `agent_engine` | `AgentEngine` | Module-level singleton instance |

**AgentEngine Class Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `process_message(user_id, message, context)` | `async → str` | Main entry: full agent cycle |
| `_build_system_prompt()` | `str` | System prompt with tool definitions |
| `_call_ai_model(messages, model)` | `async → str` | HTTP call to OpenCode Zen |
| `_execute_tool(tool_name, args)` | `str` | Run tool in sandbox |
| `_rotate_model(failed_model)` | `dict` | Select next model on failure |
| `_save_context(user_id, messages)` | `async` | Persist conversation |
| `_load_context(user_id)` | `async → list` | Retrieve conversation history |

**Agent Loop Pattern:**
```
while iterations < MAX_ITERATIONS:
    response = call_ai_model(messages, model)
    if response contains tool_call:
        result = execute_tool(tool_name, args)
        messages.append(tool_result)
    else:
        return response  # Final answer
    iterations += 1
return "Max iterations reached"
```

**Dependencies:** `config.py`, `coding_tools.py`

---

## 4. coding_tools.py

**Purpose:** 7-tool sandbox for code execution, file operations, and web search. All operations are isolated and size-limited.

**Location:** `MAIN BOT/coding_tools.py`, `CLONE BOT/coding_tools.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `CodingTools` | `class` | Tool execution engine |
| `coding_tools` | `CodingTools` | Module-level singleton instance |

**Available Tools:**
| Tool | Parameters | Description |
|------|------------|-------------|
| `read_file` | `file_path: str` | Read file contents (up to `MAX_FILE_SIZE` bytes) |
| `write_file` | `file_path: str, content: str` | Write/create files in sandbox |
| `search_files` | `pattern: str` | Glob search for files |
| `patch_file` | `file_path: str, old_text: str, new_text: str` | String replacement in files |
| `terminal` | `command: str` | Execute shell command (sandboxed) |
| `execute_code` | `code: str, language: str` | Run code in subprocess |
| `web_search` | `query: str` | Search web via API |

**Tool Schema (for AI):**
```json
{
  "name": "read_file",
  "description": "Read file contents",
  "parameters": {
    "type": "object",
    "properties": {
      "file_path": {"type": "string", "description": "Path to file"}
    },
    "required": ["file_path"]
  }
}
```

**Dependencies:** None (standalone module)

**Safety Limits:**
- `MAX_FILE_SIZE`: 10,000 bytes
- `MAX_SEARCH_RESULTS`: 5 results
- `MAX_PATCH_SIZE`: 5,000 bytes
- `MAX_OUTPUT_LENGTH`: 2,000 chars
- `MAX_TERMINAL_OUTPUT`: 2,000 chars
- All tool outputs truncated to prevent context overflow

---

## 5. payments.py

**Purpose:** Telegram Stars payment integration. Handles credit packages, invoice generation, and payment confirmation.

**Location:** `MAIN BOT/payments.py`, `CLONE BOT/payments.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `Payments` | `class` | Payment processing engine |
| `payments` | `Payments` | Module-level singleton instance |

**Payments Class Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `create_invoice(package)` | `LabeledPrice` | Generate Telegram Stars invoice |
| `handle_pre_checkout(pre_checkout_query)` | `async` | Validate & approve pre-checkout |
| `handle_successful_payment(update, context)` | `async` | Process completed payment |
| `get_user_balance(user_id)` | `int` | Query remaining credits |

**Credit Packages:**
| Package | Stars | Credits | Price |
|---------|-------|---------|-------|
| starter | 100 | 100 | 100 ⭐ |
| pro | 500 | 600 | 500 ⭐ |
| business | 1000 | 1500 | 1000 ⭐ |

**Dependencies:** `database.py`

---

## 6. memory_system.py

**Purpose:** Dual-layer memory system combining file-based conversation storage (HermesMemory) with SQLite metadata indexing (MemoryDatabase).

**Location:** `MAIN BOT/memory_system.py`, `CLONE BOT/memory_system.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `HermesMemory` | `class` | File-based conversation memory |
| `MemoryDatabase` | `class` | SQLite metadata store |
| `memory_db` | `MemoryDatabase` | Module-level SQLite instance |

**HermesMemory Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `save_conversation(user_id, messages)` | `None` | Write to `./memory/{user_id}.json` |
| `load_conversation(user_id)` | `list[dict]` | Read conversation history |
| `clear_conversation(user_id)` | `None` | Delete user's memory file |

**MemoryDatabase Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | `async` | Initialize SQLite connection |
| `save_context(user_id, messages, model)` | `None` | Store context with metadata |
| `get_context(user_id, limit)` | `list` | Retrieve recent contexts |
| `extract_keywords(messages)` | `list[str]` | Extract searchable keywords |

**Storage Paths:**
- File memory: `./memory/{telegram_id}.json`
- SQLite: `./data/memory.db`
- Agent data: `./.agent/`

**Dependencies:** None (standalone module)

---

## 7. context_engine.py (CLONE BOT only)

**Purpose:** Token tracking and automatic context compaction for long conversations. Monitors token usage and triggers compaction when approaching limits.

**Location:** `CLONE BOT/context_engine.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `ContextEngine` | `class` | Token tracking and compaction engine |
| `context_engine` | `ContextEngine` | Module-level singleton instance |

**ContextEngine Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `track_tokens(messages)` | `int` | Count tokens in message list |
| `should_compact(messages)` | `bool` | Check if compaction needed |
| `compact(messages)` | `list[dict]` | Summarize old messages |
| `get_token_usage(user_id)` | `dict` | User's token consumption stats |

**Compaction Strategy:**
- When token count exceeds threshold, summarize older messages
- Keep recent N messages in full
- Replace older messages with summaries

**Dependencies:** `config.py`

---

## 8. tools.py (CLONE BOT only)

**Purpose:** Alternate memory system implementation using SQLite only (no file-based memory).

**Location:** `CLONE BOT/tools.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `MemorySystem` | `class` | SQLite-only memory store |

**MemorySystem Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `save(user_id, key, value)` | `None` | Store key-value pair |
| `get(user_id, key)` | `str or None` | Retrieve by key |
| `search(user_id, query)` | `list[dict]` | Search stored memory |
| `delete(user_id, key)` | `None` | Remove entry |

**Dependencies:** None (uses SQLite directly)

---

## Cross-Module Relationships

```
main.py
  │
  ├─── config.py ──────────────────────── (no deps)
  │
  ├─── database.py ────────────────────── depends on: config
  │
  ├─── agent_engine.py ────────────────── depends on: config, coding_tools
  │
  ├─── coding_tools.py ────────────────── (no deps)
  │
  ├─── payments.py ────────────────────── depends on: database
  │
  └─── memory_system.py ───────────────── (no deps)

CLONE BOT extras:
  ├─── context_engine.py ──────────────── depends on: config
  └─── tools.py ───────────────────────── (no deps)
```

## Related Codemaps

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview and data flow
- [FILES.md](FILES.md) — Complete file listing
