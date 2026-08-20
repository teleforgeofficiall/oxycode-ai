# OXYGENT Architecture

> Technical deep-dive into the OXYGENT bot system

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Users                                   │
│                    (Telegram Clients)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (Bot API)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Telegram Cloud                                │
│              (Bot API servers, webhooks)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Webhook/Polling
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       main.py                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Command Router                                         │   │
│  │  • /start, /help, /status, /menu                       │   │
│  │  • /create, /voice, /search, /explain, /fix, /ui       │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Callback Router                                        │   │
│  │  • Menu navigation, Session management                 │   │
│  │  • Payment flow, Admin actions                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  agent_engine.py │  │  coding_tools.py │  │  memory_system.py │
│                  │  │                  │  │                  │
│  ┌─────────────┐ │  │  ┌─────────────┐│  │  ┌─────────────┐│
│  │ Agent Loop   │ │  │  │ File Ops    ││  │  │ HermesMemory ││
│  │ (THINK→ACT) │ │  │  │ read/write  ││  │  │ (file-based) ││
│  └─────────────┘ │  │  │ patch/search ││  │  └─────────────┘│
│  ┌─────────────┐ │  │  └─────────────┘│  │  ┌─────────────┐│
│  │ Tool Dispatch│ │  │  ┌─────────────┐│  │  │ MemoryDB    ││
│  │ (sandboxed) │ │  │  │ Terminal    ││  │  │ (SQLite)    ││
│  └─────────────┘ │  │  │ execute_code││  │  └─────────────┘│
│  ┌─────────────┐ │  │  └─────────────┘│  │  ┌─────────────┐│
│  │ Approval    │ │  │  ┌─────────────┐│  │  │ Unified     ││
│  │ System      │ │  │  │ Web Search  ││  │  │ OxygentMemory││
│  └─────────────┘ │  │  └─────────────┘│  │  └─────────────┘│
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      database.py                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Connection Pool (psycopg2 SimpleConnectionPool)        │   │
│  │  • 5-50 connections                                     │   │
│  │  • Automatic validation & recycling                     │   │
│  │  • Schema isolation via search_path                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Tables                                                │   │
│  │  • users        — Accounts, limits, voice prefs        │   │
│  │  • channels     — Force-join Telegram channels         │   │
│  │  • user_states  — Conversation flow states             │   │
│  │  • code_sessions— Code creation sessions               │   │
│  │  • payments     — Telegram Stars transactions          │   │
│  │  • broadcasts   — Broadcast message log                │   │
│  │  • settings     — Admin-configurable limits            │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQL (TLS)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL (Neon DB)                           │
│                   Cloud-hosted, serverless                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Loop Deep-Dive

### The Hermes Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent Loop (per request)                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. User Message                                             │
│     └─→ "Build a Python web scraper"                        │
│                                                              │
│  2. System Prompt Injection                                  │
│     └─→ Agent receives tools + sandbox context              │
│                                                              │
│  3. Model Call (OpenCode Zen)                                │
│     └─→ Returns: tool_calls: [write_file("scraper.py",...)] │
│                                                              │
│  4. Tool Dispatch                                            │
│     ├─→ Approval required? → Pause, show buttons            │
│     └─→ Safe? → Execute in sandbox                          │
│                                                              │
│  5. Result Feedback                                          │
│     └─→ {success: true, filepath: "/tmp/.../scraper.py"}   │
│                                                              │
│  6. Loop (max 8 turns)                                       │
│     └─→ Back to step 3 until no tool_calls                  │
│                                                              │
│  7. Return Result                                            │
│     └─→ {ok: true, files: {...}, summary: "..."}            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Rate-Limit Immunity

```
Request Flow:
                                                    
  Primary Model (hy3-free)                         
       │                                           
       ▼                                           
  ┌─────────┐    429/502    ┌─────────────────┐   
  │  Try 1  │──────────────→│ Backoff (2s)    │   
  └─────────┘               │ Try Next Model  │   
                            └────────┬────────┘   
                                     │            
                                     ▼            
                            ┌─────────────────┐   
                            │ nemotron-3.5    │   
                            │ -lightning-free │   
                            └────────┬────────┘   
                                     │            
                                     ▼            
                            ┌─────────────────┐   
                            │ nemotron-3      │   
                            │ -ultra-free     │   
                            └────────┬────────┘   
                                     │            
                                     ▼            
                            ┌─────────────────┐   
                            │ laguna-s-2.1    │   
                            │ -free           │   
                            └─────────────────┘   
```

---

## Multi-User Isolation

### Sandbox Structure

```
/tmp/oxygent_sandbox/
├── 123456789/                    # User A
│   ├── 1/                        # Session 1
│   │   ├── calculator.py
│   │   └── tests/
│   └── 2/                        # Session 2
│       ├── scraper.py
│       └── requirements.txt
└── 987654321/                    # User B
    └── 1/                        # Session 1
        └── index.html
```

### Concurrency Control

```python
# Per-user lock (one build at a time per user)
_user_locks = {
    123456789: asyncio.Lock(),  # User A builds sequentially
    987654321: asyncio.Lock(),  # User B builds sequentially
}

# Cross-user parallelism
# User A and User B run simultaneously
# User A's build blocks only User A's next build
```

---

## Database Schema

### Entity Relationship Diagram

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    users     │      │  channels    │      │   settings   │
├──────────────┤      ├──────────────┤      ├──────────────┤
│ user_id (PK) │      │ channel_id   │      │ key (PK)     │
│ username     │      │ channel_name │      │ value        │
│ first_name   │      │ channel_user │      └──────────────┘
│ bonus_msgs   │      │ added_by     │
│ msg_count    │      └──────────────┘
│ msg_date     │
│ voice_enabled│      ┌──────────────┐
│ voice_gender │      │   payments   │
│ referral_code│      ├──────────────┤
│ referred_by  │      │ id (PK)      │
└──────┬───────┘      │ user_id (FK) │
       │              │ charge_id    │
       │              │ stars        │
       │              │ credits      │
       │              └──────────────┘
       │
       │              ┌──────────────┐
       │              │code_sessions │
       │              ├──────────────┤
       └─────────────→│ id (PK)      │
                      │ user_id (FK) │
                      │ session_name │
                      │ context_data │
                      │ code_files   │
                      └──────────────┘
```

---

## Payment Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Stars Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. User taps "Buy Credits"                                 │
│     └─→ Bot shows package options                          │
│                                                             │
│  2. User selects package                                    │
│     └─→ Bot calls send_invoice()                           │
│                                                             │
│  3. Telegram shows payment dialog                           │
│     └─→ User confirms with Stars                           │
│                                                             │
│  4. PreCheckoutQuery received                               │
│     └─→ Bot answers ok=True                                │
│                                                             │
│  5. SuccessfulPayment received                              │
│     ├─→ Check charge_id uniqueness (idempotency)           │
│     ├─→ Save payment to database                           │
│     ├─→ Add bonus_messages to user                         │
│     └─→ Send confirmation to user                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Model

### Path Jail

```python
def _jail(path: str, root: str) -> Optional[str]:
    """Ensure path stays within sandbox root."""
    # Block absolute paths
    if path.startswith("/"):
        path = path.lstrip("/")
    
    # Block parent directory traversal
    if ".." in path.split("/"):
        return None
    
    # Resolve and verify containment
    resolved = os.path.normpath(os.path.join(root, path))
    if not resolved.startswith(os.path.normpath(root)):
        return None
    
    return resolved
```

### Blocked Commands

```python
BLOCKED_COMMANDS = [
    'rm -rf',      # Recursive deletion
    'mkfs',        # Format filesystem
    'dd',          # Disk operations
    'shutdown',    # System shutdown
    'reboot',      # System reboot
    'kill -9',     # Force kill
    'pkill',       # Process killing
    'killall',     # Process killing
    'systemctl',   # Service management
    'apt install', # Package installation
    'pip install', # Package installation
    'curl',        # External downloads
    'wget',        # External downloads
]
```

### Approval System

```python
# Tools requiring user approval
APPROVAL_REQUIRED_TOOLS = {
    "write_file",    # Creates/modifies files
    "patch_file",    # Edits existing files
    "terminal",      # Executes shell commands
    "execute_code",  # Runs code snippets
}
```

---

## Performance Optimizations

### Database Connection Pool

```python
# Before: Each query opened a new connection (~500ms TLS handshake)
# After: Pool reuses warm connections (<1ms)

_POOL = SimpleConnectionPool(
    minconn=5,      # Minimum warm connections
    maxconn=50,     # Maximum concurrent connections
    DATABASE_URL,
    connect_timeout=10
)
```

### Parallel Membership Checks

```python
# Before: Serial checks (n × 200ms)
results = []
for ch in channels:
    result = await check_membership(ch)  # 200ms each
    results.append(result)

# After: Parallel checks (~200ms total)
results = await asyncio.gather(*[
    check_membership(ch) for ch in channels
])
```

### Typing Indicator Refresh

```python
# Telegram's typing action expires after ~5s
# Keep refreshing while AI is processing
async def _typing_while(update, context, coro):
    task = asyncio.ensure_future(coro)
    while not task.done():
        await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
    return await task
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      VPS / Cloud Server                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Main Bot       │  │  Clone Bot       │                  │
│  │  (Production)   │  │  (Staging)       │                  │
│  │  Schema: public │  │  Schema: clone   │                  │
│  └────────┬────────┘  └────────┬────────┘                  │
│           │                    │                            │
│           └────────────────────┘                            │
│                        │                                    │
│                        ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              PostgreSQL (Neon DB)                    │   │
│  │  ┌─────────────┐  ┌─────────────┐                   │   │
│  │  │ public.*    │  │ clone.*     │                   │   │
│  │  │ (prod data) │  │ (test data) │                   │   │
│  │  └─────────────┘  └─────────────┘                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              /tmp/oxygent_sandbox/                   │   │
│  │  ├─ 123456789/  (User A sessions)                  │   │
│  │  └─ 987654321/  (User B sessions)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Monitoring & Observability

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `active_users` | Users in conversation flow | > 100 |
| `pool_exhausted` | Connection pool exhaustion events | > 0 |
| `ai_failures` | All models down errors | > 5/min |
| `build_timeouts` | Agent loop timeouts (>900s) | > 2/min |
| `payment_duplicates` | Duplicate payment attempts | > 0 |

### Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Module-specific loggers
logger = logging.getLogger(__name__)
logger.error(f"Build failed: {error}")
logger.warning(f"Rate limit on model: {model}")
```

---

## Future Considerations

### Potential Enhancements

1. **WebSocket Support** — Real-time streaming of agent progress
2. **Docker Sandbox** — Stronger isolation than filesystem jail
3. **Redis Caching** — Cache frequent database queries
4. **Prometheus Metrics** — Export metrics for Grafana dashboards
5. **CI/CD Pipeline** — Automated testing and deployment
6. **Multi-Language Support** — Localized bot messages

### Scaling Strategies

1. **Horizontal Scaling** — Multiple bot instances behind load balancer
2. **Database Read Replicas** — Separate read/write paths
3. **Queue System** — Redis/RabbitMQ for build job queuing
4. **CDN** — Serve generated files via Cloudflare/R2

---

**Author:** OXYCODE TEAM
