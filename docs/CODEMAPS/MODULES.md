# Modules Codemap

**Last Updated:** 2026-08-21

## Module Dependency Graph

```
                         config.py
                        /    |    \
                       /     |     \
              database.py  agent_engine.py  error_fix.py
                 |           /        \           |
             payments.py  coding_tools.py  cloudflare_deploy.py
                          (standalone)          |
                                         cloudflare_oauth.py
                                               |
                                          database.py

  MAIN BOT only:
  - api_server.py
  - cloudflare_deploy.py
  - cloudflare_oauth.py
  - error_fix.py
  - project_analyzer.py
  - deploy_vps.py
```

---

## 1. config.py

**Purpose:** Central configuration hub. Loads all environment variables, defines AI model endpoints, bot messages, and system limits.

**Location:** `MAIN BOT/config.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `BOT_TOKEN` | `str` | Telegram Bot API token |
| `ADMIN_IDS` | `list[int]` | Admin user IDs (default: 8972944701, 7371674958) |
| `AGENT_NAME` | `str` | Bot display name ("OXYCODE") |
| `OPENCODE_ZEN_BASE_URL` | `str` | AI API base URL |
| `OPENCODE_ZEN_MODEL` | `str` | Primary AI model (default: mimo-v2.5-free) |
| `OPENCODE_ZEN_FALLBACKS` | `list[str]` | Fallback models for rate-limit rotation |
| `DATABASE_URL` | `str` | PostgreSQL connection string |
| `WELCOME_MESSAGE` | `str` | HTML-formatted welcome message |
| `HELP_MESSAGE` | `str` | HTML-formatted help message |
| `SYSTEM_PROMPT` | `str` | Full AI personality and behavior rules |
| `MAX_SESSIONS` | `int` | Max code sessions per user (5) |
| `REFERRAL_BONUS` | `int` | Credits for referral (20) |
| `DEFAULT_DAILY_LIMIT` | `int` | Free tier daily limit (20) |
| `MAINTENANCE_MODE` | `bool` | Global maintenance toggle |

**Dependencies:** `os`, `dotenv`

**AI Models (Free Tier):**
- Primary: `mimo-v2.5-free`
- Fallbacks: `deepseek-v4-flash-free`, `hy3-free`, `nemotron-3.5-lightning-free`, `nemotron-3-ultra-free`, `laguna-s-2.1-free`

---

## 2. database.py

**Purpose:** PostgreSQL database layer using psycopg2 with connection pooling. Handles all persistent storage for users, sessions, payments, channels, deployments, and Cloudflare tokens.

**Location:** `MAIN BOT/database.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `_POOL` | `SimpleConnectionPool` | Connection pool (5-50 connections) |
| `get_db()` | `function` | Get pooled database connection |
| `add_user(user_id, username, first_name)` | `function` | Add or update user |
| `get_user(user_id)` | `function` | Get user by Telegram ID |
| `update_voice_pref(user_id, enabled, gender)` | `function` | Set voice preferences |
| `get_voice_pref(user_id)` | `function` | Get voice preferences |
| `get_maintenance_mode()` | `function` | Check maintenance status |
| `set_maintenance_mode(enabled)` | `function` | Toggle maintenance mode |
| `create_session(user_id, name, type)` | `function` | Create code session |
| `get_user_sessions(user_id)` | `function` | Get user's sessions |
| `payment_exists(charge_id)` | `function` | Idempotency check |
| `save_payment(...)` | `function` | Record Telegram Stars payment |
| `get_setting(key)` | `function` | Get admin setting |
| `set_setting(key, value)` | `function` | Set admin setting |
| `get_user_profile(user_id)` | `function` | Get full user profile (single query) |
| `get_bot_stats()` | `function` | Get comprehensive bot statistics |
| `add_deployment(...)` | `function` | Record deployment |
| `get_user_deployments(uid)` | `function` | Get user's deployments |

**Database Tables:**
| Table | Purpose |
|-------|---------|
| `users` | User accounts, limits, voice prefs, referral codes |
| `channels` | Force-join Telegram channels |
| `user_states` | Conversation flow states |
| `code_sessions` | Code creation sessions with context |
| `payments` | Telegram Stars transactions |
| `broadcasts` | Broadcast message log |
| `settings` | Admin-configurable limits |
| `workers` | Cloudflare Worker hosting info |
| `deployments` | Deployed projects (Vercel/Cloudflare) |
| `projects` | Mini App projects |
| `daily_messages` | Daily message tracking for Mini App |
| `cloudflare_accounts` | Per-user Cloudflare OAuth tokens |

**Dependencies:** `psycopg2`, `config.py`

**Safety:**
- Refuses to start without valid PostgreSQL URL (no SQLite fallback)
- Schema isolation via `OXYGENT_SCHEMA` env var
- All user_id columns are BIGINT (Telegram 64-bit IDs)
- Connection pool with automatic validation and recycling

---

## 3. agent_engine.py

**Purpose:** Hermes-style autonomous coding agent. Implements the THINK→ACT→OBSERVE loop with tool calling, model rotation, and sandboxed execution.

**Location:** `MAIN BOT/agent_engine.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `agent_build(uid, sid, user_message, ...)` | `async function` | Main entry: full agent build cycle |

**Agent Build Flow:**
```
agent_build(uid, sid, message)
  → Create sandbox: /tmp/oxygent_sandbox/{uid}/{sid}/
  → Load conversation context
  → Build system prompt with tool definitions
  → Enter agent loop (max 8 turns):
      → Call OpenCode Zen API
      → Parse tool_calls from response
      → Execute tool in sandbox
      → Feed result back as role:"tool" message
  → Collect all files from sandbox
  → Return {ok, files, summary, session_name}
```

**Model Rotation:**
```
Primary (mimo-v2.5-free)
  → 429/502? → Backoff 2s → Try next fallback
  → deepseek-v4-flash-free
  → hy3-free
  → nemotron-3.5-lightning-free
  → nemotron-3-ultra-free
  → laguna-s-2.1-free
```

**Safety Features:**
- Path jail prevents sandbox escapes (no ".." or absolute paths)
- Per-user asyncio.Lock serializes builds
- Blocked commands: rm -rf, mkfs, dd, shutdown, pip install, curl, wget
- Approval required for: write_file, patch_file, terminal, execute_code

**Dependencies:** `config.py`, `coding_tools.py`

---

## 4. coding_tools.py

**Purpose:** 7-tool sandbox for code execution, file operations, and web search. All operations are isolated to the sandbox directory.

**Location:** `MAIN BOT/coding_tools.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `read_file(filepath)` | `async function` | Read file content |
| `write_file(filepath, content)` | `async function` | Create/overwrite files |
| `search_files(pattern, path)` | `async function` | Search by filename or content |
| `patch_file(filepath, old, new)` | `async function` | Find/replace edits |
| `terminal(command, timeout)` | `async function` | Execute sandboxed shell commands |
| `execute_code(code, language)` | `async function` | Run Python/JS snippets |
| `web_search(query)` | `async function` | DuckDuckGo search |

**Safety Limits:**
- `MAX_FILE_SIZE`: 10,000 bytes
- `MAX_SEARCH_RESULTS`: 5
- `MAX_PATCH_SIZE`: 5,000 bytes
- `MAX_OUTPUT_LENGTH`: 2,000 chars
- Blocked commands list enforced

**Dependencies:** None (standalone module)

---

## 5. payments.py

**Purpose:** Telegram Stars payment integration. Handles credit packages, invoice generation, and payment confirmation with idempotency.

**Location:** `MAIN BOT/payments.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `STAR_PACKAGES` | `list[dict]` | Available credit packages |
| `get_buy_keyboard()` | `function` | Inline keyboard for package selection |
| `create_invoice(package)` | `function` | Generate Telegram Stars invoice |
| `handle_pre_checkout(query)` | `async function` | Validate & approve pre-checkout |
| `handle_successful_payment(update)` | `async function` | Process completed payment |

**Credit Packages:**
| Stars | Credits | Price/Credit |
|-------|---------|--------------|
| 3 | 10 | 0.30 ⭐ |
| 10 | 35 | 0.29 ⭐ |
| 30 | 120 | 0.25 ⭐ |
| 100 | 400 | 0.25 ⭐ |
| 300 | 1500 | 0.20 ⭐ |

**Dependencies:** `database.py`, `telegram` (LabeledPrice, InlineKeyboardButton)

---

## 6. memory_system.py

**Purpose:** Triple-layer memory system combining file-based storage (HermesMemory), PostgreSQL (MemoryDatabase), and unified interface (OxygentMemory).

**Location:** `MAIN BOT/memory_system.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `HermesMemory` | `class` | File-based memory (MEMORY.md, USER.md) |
| `MemoryDatabase` | `class` | PostgreSQL-backed structured storage |
| `OxygentMemory` | `class` | Unified interface combining both layers |
| `get_memory(user_id)` | `function` | Factory for OxygentMemory instances |

**HermesMemory (File-based):**
- `MEMORY.md`: Agent's personal notes about the user (4000 char limit)
- `USER.md`: User profile (2000 char limit)
- Entry delimiter: `§` (Hermes style)

**MemoryDatabase (PostgreSQL):**
- Structured key-value storage
- Conversation history tracking
- Category-based organization

**Auto-Detection:**
- Names ("mera naam Rahul" → name: Rahul)
- Favorites ("mujhe pizza pasand" → favourite: pizza)
- Age, City, Occupation from natural language

**Dependencies:** None (standalone module)

---

## 7. context_engine.py

**Purpose:** Token tracking and automatic context compaction. Monitors token usage and triggers summarization when approaching limits.

**Location:** `MAIN BOT/context_engine.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `ContextEngine` | `class` | Token tracking and compaction engine |

**ContextEngine Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `set_system_prompt(prompt)` | `None` | Set system prompt (max 3000 chars) |
| `add_message(role, content)` | `None` | Add message, estimate tokens, auto-compact |
| `_compact()` | `None` | Summarize old messages when >80% capacity |

**Limits:**
- `MAX_CONTEXT_TOKENS`: 4,000
- `COMPACTION_THRESHOLD`: 0.8 (compact at 80%)
- Token estimation: ~4 chars per token

**Dependencies:** None (standalone module)

---

## 8. api_server.py (MAIN BOT only)

**Purpose:** FastAPI backend for the Telegram Mini App web dashboard. Handles JWT authentication, project management, AI chat proxy, Cloudflare deployment, and error fixing.

**Location:** `MAIN BOT/api_server.py`

**Key Endpoints:**
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
| GET | `/api/deployments` | List deployed projects |
| GET | `/api/cloudflare/status` | Check Cloudflare connection |
| GET | `/api/cloudflare/auth-url` | Get OAuth authorization URL |
| GET | `/api/cloudflare/callback` | Handle OAuth callback |
| DELETE | `/api/cloudflare/disconnect` | Disconnect Cloudflare account |

**Dependencies:** `fastapi`, `jwt`, `database.py`, `config.py`, `error_fix.py`, `cloudflare_oauth.py`, `cloudflare_deploy.py`

**Auth Flow:**
```
Frontend sends Telegram initData
  → Verify HMAC signature with BOT_TOKEN
  → Extract user_id, username, first_name
  → Generate JWT (7-day expiry)
  → Return token + user profile
```

**Middleware:**
- CORS (allow all origins for dev)
- MaintenanceMiddleware (blocks non-admins when maintenance ON)

---

## 10. cloudflare_oauth.py (MAIN BOT only)

**Purpose:** Per-user Cloudflare account connection via OAuth. Each user connects their own CF account for deploying projects.

**Location:** `MAIN BOT/cloudflare_oauth.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `get_cloudflare_account(telegram_id)` | `function` | Get user's CF account info |
| `is_cloudflare_connected(telegram_id)` | `function` | Check if user has connected CF account |
| `save_cloudflare_account(...)` | `function` | Save CF account credentials |
| `remove_cloudflare_account(telegram_id)` | `function` | Disconnect CF account |
| `cf_api_get(telegram_id, path)` | `function` | Authenticated CF API GET |
| `cf_api_post(telegram_id, path, data)` | `function` | Authenticated CF API POST |
| `cf_api_put(telegram_id, path, data)` | `function` | Authenticated CF API PUT |

**OAuth Flow:**
```
User clicks "Connect Cloudflare"
  → Redirect to CF OAuth authorization
  → User authorizes
  → CF redirects back with auth code
  → Exchange code for API token
  → Save to cloudflare_accounts table
```

**Required CF Token Scopes:**
- Workers Scripts: Edit
- Workers KV Storage: Edit
- Workers R2 Storage: Edit
- Cloudflare Pages: Edit
- Zone Settings: Read
- DNS: Read/Write

**Database Table:** `cloudflare_accounts`
- `user_id` (BIGINT, PK)
- `api_token` (TEXT)
- `account_id` (TEXT)
- `account_name` (TEXT)
- `email` (TEXT)
- `connected_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

**Dependencies:** `database.py`, `aiohttp`

---

## 11. cloudflare_deploy.py (MAIN BOT only)

**Purpose:** Deploy user projects to Cloudflare Pages and Workers using the user's connected Cloudflare account.

**Location:** `MAIN BOT/cloudflare_deploy.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `deploy_to_pages(telegram_id, project_name, files)` | `async function` | Deploy static site to CF Pages |
| `deploy_to_workers(telegram_id, script_name, script)` | `async function` | Deploy worker script |

**Deployment Flow:**
```
Agent calls deploy_website/deploy_bot tool
  → Get user's CF token from database
  → Create zip of project files
  → POST to CF Pages API or PUT to Workers API
  → Return live URL
```

**Dependencies:** `cloudflare_oauth.py`

---

## 12. error_fix.py (MAIN BOT only)

**Purpose:** AI-powered error detection and auto-repair for deployed projects. Analyzes errors and generates fixes using OpenCode AI.

**Location:** `MAIN BOT/error_fix.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `build_fix_prompt(error_type, error_message, project_files, ...)` | `function` | Build AI prompt for error analysis |
| `analyze_error(...)` | `async function` | Get AI fix suggestion |
| `apply_fix(...)` | `async function` | Apply fix and redeploy |

**Error Types Handled:**
- HTTP errors (404, 500, CORS)
- JavaScript runtime errors
- Build/compilation errors
- Missing resources
- Deployment failures

**Dependencies:** `config.py`

---

## 13. project_analyzer.py (MAIN BOT only)

**Purpose:** Auto-detects project type, tech stack, and deployment target from user prompts using keyword matching (no AI call needed).

**Location:** `MAIN BOT/project_analyzer.py`

**Key Exports:**
| Export | Type | Description |
|--------|------|-------------|
| `analyze_prompt(prompt)` | `function` | Analyze prompt → project metadata |

**Return Shape:**
```python
{
    "projectType": "website" | "telegram-bot" | "miniapp" | "api" | ...,
    "techStack": ["react", "typescript", "tailwind"],
    "deploymentTarget": "cloudflare-pages" | "cloudflare-workers" | "vercel" | "none",
    "files": ["index.html", "style.css"],
    "runCommand": "npm start",
    "description": "One-line description"
}
```

**Dependencies:** None (standalone module)

---

## 14. deploy_vps.py (MAIN BOT only)

**Purpose:** SSH-based VPS deployment script using paramiko. Uploads bot + API to a remote server.

**Location:** `MAIN BOT/deploy_vps.py`

**Key Functions:**
| Function | Description |
|----------|-------------|
| `connect_vps()` | SSH connection to VPS |
| `run_cmd(client, cmd)` | Execute remote command |
| `upload_file(sftp, local, remote)` | Upload file via SFTP |
| `deploy()` | Full deployment sequence |

**Dependencies:** `paramiko`

---

## Cross-Module Relationships

```
MAIN BOT:
  main.py
    ├── config.py ─────────────────── (no deps)
    ├── database.py ───────────────── depends on: config
    ├── agent_engine.py ───────────── depends on: config, coding_tools
    ├── coding_tools.py ───────────── (no deps)
    ├── payments.py ───────────────── depends on: database
    ├── memory_system.py ──────────── (no deps)
    ├── context_engine.py ─────────── (no deps)
    ├── api_server.py ─────────────── depends on: database, config, error_fix
    ├── cloudflare_oauth.py ───────── depends on: database
    ├── cloudflare_deploy.py ──────── depends on: cloudflare_oauth
    ├── error_fix.py ──────────────── depends on: config
    ├── project_analyzer.py ───────── (no deps)
    └── deploy_vps.py ─────────────── (no deps)
```

## Related Codemaps

- [ARCHITECTURE.md](ARCHITECTURE.md) — System overview and data flow
- [FILES.md](FILES.md) — Complete file listing
