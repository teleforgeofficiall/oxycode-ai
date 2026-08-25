"""
OXYCODE AI — VPS Backend API
=============================

FastAPI server for the Telegram Mini App.
Handles authentication, project management, and AI chat proxy.

Endpoints:
    POST /api/auth/telegram   — Verify Telegram initData, return JWT + user
    GET  /api/user/me         — Get current user profile
    GET  /api/projects        — List user's projects
    POST /api/projects        — Create new project
    GET  /api/projects/:id    — Get project details
    DELETE /api/projects/:id  — Delete project
    POST /api/chat            — Send message to AI, get response
    GET  /api/limits          — Get user's daily limits
    POST /api/deploy          — Deploy to Cloudflare
    POST /api/fix             — AI error analysis
    POST /api/fix/apply       — Apply fixes and redeploy
"""

import os
import hashlib
import hmac
import time
import json
import logging
import jwt
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Depends, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("oxycode-api")

# ==================== CONFIG ====================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
JWT_SECRET = os.getenv("JWT_SECRET", "oxycode-miniapp-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 7 * 24  # 7 days

OPENCODE_ZEN_BASE_URL = os.getenv("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1")
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")
# Primary: Ox Alpha Free (x-preview-f-free) — fastest; fails fast (503 <0.5s) when upstream down.
OPENCODE_ZEN_MODEL = os.getenv("OPENCODE_ZEN_MODEL", "x-preview-f-free")
OPENCODE_ZEN_FALLBACKS = os.getenv(
    "OPENCODE_ZEN_FALLBACKS",
    "mimo-v2.5-free,deepseek-v4-flash-free,hy3-free,nemotron-3.5-lightning-free,nemotron-3-ultra-free,laguna-s-2.1-free"
).split(",")

# System prompt for the Mini App chat (WebSocket path).
# This is a conversational prompt — the full OXYGENT agent prompt in config.py
# references tools (write_file, terminal, deploy_website) that do NOT exist in
# this path, so we keep the identity but drop tool instructions.
CHAT_SYSTEM_PROMPT = os.getenv("CHAT_SYSTEM_PROMPT", """You are OXYGENT, the AI inside the OXYCODE Telegram Mini App.

IDENTITY
- You are an autonomous AI agent that builds, deploys and ships software.
- If asked which model you are: "I'm OXYGENT — an autonomous AI agent." Never mention model names or providers.

HOW TO RESPOND
1. CASUAL CHAT ("hi", "hey", "hello", "kaise ho", "thanks") → Reply warmly and briefly. Ask what they'd like to build. NO tools, NO code dumps.
2. ASK/EXPLAIN ("what is X", "explain recursion", "how does this work") → Explain clearly and concisely with markdown if helpful.
3. BUILD/CREATE ("bnao", "build a todo app", "make a bot", "write a script") → Describe a short plan (stack + files + steps) and tell them what you will build. Keep it under 15 lines.
4. FIX/EDIT ("fix this error", paste code) → Identify the problem and show the corrected code in markdown code blocks with the language tag.

RULES
- ALWAYS reply with actual text. NEVER return an empty response.
- Match the user's language (English / Hinglish / Hindi).
- Keep replies concise. Use markdown formatting for code.
- Never expose API keys or secrets.""")

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Admin IDs — only these users can access the bot
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8972944701,7371674958").split(",") if x.strip()]

# Daily limits
FREE_DAILY_LIMIT = 20


# ==================== DATABASE ====================

def get_db():
    """Get a database connection."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def db_get_setting(key, default=None):
    """Get a setting from the settings table."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def db_get_user(telegram_id: int):
    """Get user by Telegram ID."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (telegram_id,))
    user = cur.fetchone()
    conn.close()
    return dict(user) if user else None


def db_is_maintenance_mode():
    """Check if bot is in maintenance mode."""
    return db_get_setting("maintenance_mode", "false") == "true"


def db_is_chat_admin_only():
    """Check if chat access is restricted to admins only."""
    return db_get_setting("chat_admin_only", "false") == "true"


# ---- Async DB helpers -------------------------------------------------------
# psycopg2 is synchronous; calling it directly inside async handlers blocks the
# entire event loop while Neon (remote, cold-start prone) responds. All hot-path
# DB access must go through asyncio.to_thread.

async def run_db(fn, *args, **kwargs):
    """Run a blocking DB function off the event loop.

    Neon can drop an idle pooled connection mid-call (InterfaceError:
    connection already closed). One transparent retry gets a fresh
    connection from get_db()'s validation path and the call succeeds.
    """
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except psycopg2.InterfaceError:
        logger.warning(f"[db] stale connection in {fn.__name__}, retrying once")
        return await asyncio.to_thread(fn, *args, **kwargs)


_MAINT_TTL = 10.0  # seconds
_maint_cache = {"value": False, "ts": 0.0}


async def get_maintenance_mode() -> bool:
    """Maintenance flag with a short TTL cache so per-request middleware never
    blocks on a remote DB round-trip."""
    now = time.time()
    if now - _maint_cache["ts"] < _MAINT_TTL:
        return _maint_cache["value"]
    try:
        value = await run_db(db_is_maintenance_mode)
        _maint_cache["value"] = bool(value)
        _maint_cache["ts"] = now
        return _maint_cache["value"]
    except Exception as e:
        logger.warning(f"maintenance check failed, using cached={_maint_cache['value']}: {e}")
        return _maint_cache["value"]


def bust_maintenance_cache():
    _maint_cache["ts"] = 0.0


_ADMIN_ONLY_TTL = 10.0  # seconds
_admin_only_cache = {"value": False, "ts": 0.0}


async def get_chat_admin_only() -> bool:
    """Admin-only chat flag with a short TTL cache (same pattern as
    get_maintenance_mode) so WS connects never block on a remote DB."""
    now = time.time()
    if now - _admin_only_cache["ts"] < _ADMIN_ONLY_TTL:
        return _admin_only_cache["value"]
    try:
        value = await run_db(db_is_chat_admin_only)
        _admin_only_cache["value"] = bool(value)
        _admin_only_cache["ts"] = now
        return _admin_only_cache["value"]
    except Exception as e:
        logger.warning(f"chat_admin_only check failed, using cached={_admin_only_cache['value']}: {e}")
        return _admin_only_cache["value"]


def bust_chat_admin_only_cache():
    _admin_only_cache["ts"] = 0.0


def _db_ping_sync():
    """Single cheap query to keep the remote DB awake."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        conn.close()


async def _start_db_keepalive():
    """Neon free tier suspends compute after ~5min idle; the next query then
    stalls for seconds. Ping every 4 minutes to keep it warm."""

    async def _loop():
        while True:
            try:
                await asyncio.to_thread(_db_ping_sync)
            except Exception as e:
                logger.warning(f"[keepalive] db ping failed: {e}")
            await asyncio.sleep(240)

    asyncio.create_task(_loop())
    logger.info("[keepalive] db keep-alive started (every 240s)")


def db_get_user_msg_count(telegram_id: int, date: str):
    """Get user's message count for a given date."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(count), 0) FROM daily_messages WHERE user_id = %s AND date = %s",
        (telegram_id, date),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


def db_increment_msg_count(telegram_id: int, date: str):
    """Increment user's message count for today."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO daily_messages (user_id, date, count)
           VALUES (%s, %s, 1)
           ON CONFLICT (user_id, date) DO UPDATE SET count = daily_messages.count + 1""",
        (telegram_id, date),
    )
    conn.commit()
    conn.close()


# ==================== TELEGRAM AUTH ====================

def verify_telegram_init_data(init_data: str) -> dict:
    """Verify Telegram Mini App initData using HMAC-SHA256.

    Returns the validated user dict if valid, raises ValueError if not.
    Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not configured")

    # Parse the initData string
    params = {}
    for item in init_data.split("&"):
        if "=" in item:
            key, value = item.split("=", 1)
            params[key] = unquote(value)

    if "hash" not in params:
        raise ValueError("Missing hash in initData")

    received_hash = params.pop("hash")

    # Build the data-check-string
    # Sort keys alphabetically and join as key=value\n
    data_check_lines = []
    for key in sorted(params.keys()):
        data_check_lines.append(f"{key}={params[key]}")
    data_check_string = "\n".join(data_check_lines)

    # Compute HMAC-SHA256 using bot_token as secret
    secret_key = hmac.new(
        "WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if computed_hash != received_hash:
        raise ValueError("Invalid hash — initData verification failed")

    # Check auth_date (must be within 10 minutes)
    auth_date = int(params.get("auth_date", 0))
    now = int(time.time())
    if now - auth_date > 600:
        raise ValueError("initData expired (>10 minutes old)")

    # Parse user data
    user_data = params.get("user")
    if user_data:
        try:
            user = json.loads(user_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid user JSON in initData")
    else:
        raise ValueError("Missing user data in initData")

    return user


def create_jwt_token(telegram_id: int) -> str:
    """Create a JWT token for the user."""
    now = int(time.time())
    payload = {
        "sub": str(telegram_id),
        "iat": now,
        "exp": now + JWT_EXPIRY_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> int:
    """Decode JWT token and return telegram_id. Raises ValueError if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
        raise ValueError("Invalid or expired token")


# ==================== FASTAPI ====================

app = FastAPI(title="OXYCODE AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MAINTENANCE MIDDLEWARE ====================

class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Block non-admin users when maintenance mode is ON."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip health check and static files
        path = request.url.path
        if path in ("/api/health", "/api/status", "/docs", "/openapi.json", "/api/auth/telegram", "/api/admin/maintenance/toggle", "/api/auth/csrf-token") or path.startswith("/static"):
            return await call_next(request)
        
        # Check maintenance mode (cached, non-blocking)
        try:
            maintenance = await get_maintenance_mode()
        except Exception:
            maintenance = False
        
        if not maintenance:
            return await call_next(request)
        
        # Maintenance is ON — only allow admins
        auth_header = request.headers.get("authorization", "")
        is_admin = False
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                telegram_id = int(payload["sub"])
                is_admin = telegram_id in ADMIN_IDS
                if not is_admin:
                    logger.warning(f"[maintenance] admin bypass failed: sub={telegram_id} not in {ADMIN_IDS}")
            except Exception as e:
                logger.warning(f"[maintenance] admin token decode failed: {type(e).__name__}: {e}", exc_info=True)
        else:
            logger.warning(f"[maintenance] blocked (no bearer header) path={path}")

        # Admin passes through — call_next OUTSIDE try/except so endpoint
        # errors propagate normally instead of becoming 503 maintenance.
        if is_admin:
            return await call_next(request)

        # Non-admin or no token — block
        return JSONResponse(
            status_code=503,
            content={
                "error": "maintenance",
                "message": "Bot is under maintenance. Please try again later.",
            },
        )


app.add_middleware(MaintenanceMiddleware)


@app.on_event("startup")
async def _register_db_keepalive():
    await _start_db_keepalive()


async def get_current_user(authorization: str = Header(None)) -> int:
    """Dependency: extract telegram_id from JWT in Authorization header."""
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    token = authorization.replace("Bearer ", "")
    try:
        return decode_jwt_token(token)
    except ValueError:
        raise HTTPException(401, "Invalid or expired token")


# ==================== MODELS ====================

class TelegramAuthRequest(BaseModel):
    initData: str


class ChatRequest(BaseModel):
    message: str
    projectId: Optional[int] = None


class ProjectCreateRequest(BaseModel):
    name: str
    prompt: str
    projectType: Optional[str] = None


class ChatCreateRequest(BaseModel):
    title: str = "New Chat"


class ChatRenameRequest(BaseModel):
    title: str


class ChatMessageRequest(BaseModel):
    message: str


class AgentSessionRequest(BaseModel):
    query: str
    projectType: Optional[str] = "app"
    behaviorType: Optional[str] = None
    images: Optional[list] = []


# ==================== WEBSOCKET MANAGER ====================

class ConnectionManager:
    def __init__(self):
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, chat_id: int):
        await websocket.accept()
        if chat_id not in self.active:
            self.active[chat_id] = []
        self.active[chat_id].append(websocket)

    def disconnect(self, websocket: WebSocket, chat_id: int):
        if chat_id in self.active:
            self.active[chat_id] = [ws for ws in self.active[chat_id] if ws != websocket]
            if not self.active[chat_id]:
                del self.active[chat_id]

    async def send_to_chat(self, chat_id: int, message: dict):
        if chat_id in self.active:
            for ws in self.active[chat_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass


ws_manager = ConnectionManager()

# CSRF token store (simple in-memory)
_csrf_tokens: dict[str, float] = {}

def _generate_csrf_token() -> str:
    import secrets
    token = secrets.token_hex(32)
    _csrf_tokens[token] = time.time() + 7200
    return token

def _validate_csrf_token(token: str) -> bool:
    if token in _csrf_tokens:
        if time.time() < _csrf_tokens[token]:
            return True
        del _csrf_tokens[token]
    return False


# ==================== ROUTES ====================

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "oxycode-ai-backend"}


@app.get("/api/status")
async def status():
    """Public endpoint — returns maintenance mode status."""
    return {"maintenance": await get_maintenance_mode()}


@app.post("/api/error")
async def report_error(request: Request):
    """Public endpoint — receives frontend error reports for debugging."""
    try:
        body = await request.json()
        logger.error(f"[FRONTEND ERROR] {json.dumps(body, default=str)[:500]}")
    except Exception:
        pass
    return {"ok": True}


# ==================== CSRF TOKEN ENDPOINT ====================

@app.get("/api/auth/csrf-token")
async def csrf_token():
    token = _generate_csrf_token()
    return {"data": {"token": token, "expiresIn": 7200}}


# ==================== AGENT SESSION ENDPOINT ====================

@app.post("/api/agent")
async def create_agent_session(
    request: Request,
    telegram_id: int = Depends(get_current_user),
):
    body = await request.json()
    query = body.get("query", "")
    project_type = body.get("projectType", "app")
    behavior_type = body.get("behaviorType") or "phasic"

    # Validate CSRF token
    csrf_header = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
    if not csrf_header or not _validate_csrf_token(csrf_header):
        return JSONResponse(
            status_code=403,
            content={"error": {"message": "Invalid or missing CSRF token", "type": "csrf_violation"}},
        )

    # Create chat in database (off event loop)
    def _create_chat():
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "INSERT INTO chats (user_id, title) VALUES (%s, %s) RETURNING id, title, created_at, updated_at",
                (telegram_id, query[:100] if query else "New Chat"),
            )
            chat = dict(cur.fetchone())
            conn.commit()
            return chat
        finally:
            conn.close()

    chat = await run_db(_create_chat)

    chat_id = chat["id"]

    # Return NDJSON stream
    async def stream():
        yield json.dumps({"template": {"files": []}}) + "\n"
        yield json.dumps({"behaviorType": behavior_type}) + "\n"
        yield json.dumps({"projectType": project_type}) + "\n"
        yield json.dumps({"agentId": str(chat_id)}) + "\n"
        ws_base = os.environ.get("WEBSOCKET_BASE_URL", "ws://153.75.247.105:8000")
        yield json.dumps({"websocketUrl": f"{ws_base}/ws/{chat_id}"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


# ==================== WEBSOCKET ENDPOINT ====================

def _load_chat_history_sync(chat_id: int, limit: int = 20):
    """Load recent messages for a chat (oldest→newest). Blocking — call via run_db."""
    history = []
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT role, content FROM (
                SELECT id, role, content, created_at
                FROM messages WHERE chat_id = %s
                ORDER BY created_at DESC LIMIT %s
            ) t ORDER BY created_at ASC
            """,
            (chat_id, limit),
        )
        for row in cur.fetchall():
            if row["role"] in ("user", "assistant") and row["content"]:
                history.append({"role": row["role"], "content": row["content"]})
    finally:
        conn.close()
    return history


async def _load_chat_history(chat_id: int, limit: int = 20):
    try:
        return await run_db(_load_chat_history_sync, chat_id, limit)
    except Exception as e:
        logger.warning(f"[ws:{chat_id}] history load failed: {e}")
        return []


def _persist_message_sync(chat_id: int, role: str, content: str, model=None):
    """Persist a chat message. Blocking — call via run_db."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (chat_id, role, content, model) VALUES (%s, %s, %s, %s)",
            (chat_id, role, content, model),
        )
        conn.commit()
    finally:
        conn.close()


async def _persist_message(chat_id: int, role: str, content: str, model=None):
    try:
        await run_db(_persist_message_sync, chat_id, role, content, model)
    except Exception as e:
        logger.warning(f"[ws:{chat_id}] persist {role} failed: {e}")


def _exec_db(sql: str, params=()):
    """Run a write statement. Blocking — call via run_db."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _load_state_rows_sync(chat_id: int):
    """Full ordered history for state restore. Blocking — call via run_db."""
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT role, content, created_at FROM messages WHERE chat_id = %s ORDER BY created_at",
            (chat_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


async def _call_llm(messages: list):
    """Call OpenCode Zen with model fallback chain. Returns (reply, model_used)."""
    models = [OPENCODE_ZEN_MODEL] + [m for m in OPENCODE_ZEN_FALLBACKS if m != OPENCODE_ZEN_MODEL]
    last_err = ""
    async with aiohttp.ClientSession() as http:
        for model in models:
            payload = {"model": model, "messages": messages, "stream": False}
            logger.info(f"[llm] trying model={model} msgs={len(messages)}")
            for attempt in range(2):
                try:
                    headers = {"Content-Type": "application/json", "User-Agent": "opencode/1.18.16"}
                    if OPENCODE_API_KEY:
                        headers["Authorization"] = f"Bearer {OPENCODE_API_KEY}"
                    async with http.post(
                        f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            reply = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                            usage = result.get("usage", {})
                            logger.info(
                                f"[llm] model={model} OK len={len(reply)} "
                                f"prompt_tokens={usage.get('prompt_tokens')} completion_tokens={usage.get('completion_tokens')}"
                            )
                            if reply and reply.strip():
                                return reply.strip(), model
                            # Empty content — treat as retryable failure
                            last_err = f"{model}: empty content"
                            logger.warning(f"[llm] {last_err}, body={json.dumps(result)[:200]}")
                            break
                        body = await resp.text()
                        last_err = f"{model} HTTP {resp.status}: {body[:120]}"
                        logger.warning(f"[llm] {last_err} (attempt {attempt + 1}/2)")
                        if resp.status in (429, 500, 502, 503, 504) and attempt < 1:
                            await asyncio.sleep(0.5)
                            continue
                        break
                except Exception as e:
                    last_err = f"{model} {type(e).__name__}: {str(e)[:120]}"
                    logger.warning(f"[llm] {last_err} (attempt {attempt + 1}/2)")
                    if attempt < 1:
                        await asyncio.sleep(0.5)
                        continue
                    break
    logger.error(f"[llm] all models failed. Last error: {last_err}")
    return None, last_err


async def _run_with_heartbeat(coro, websocket: WebSocket, chat_id: int, interval: float = 10.0):
    """Await a coroutine while sending ping frames so proxies don't kill the
    idle WebSocket during long LLM calls."""
    task = asyncio.ensure_future(coro)
    while True:
        done, _pending = await asyncio.wait({task}, timeout=interval)
        if done:
            return task.result()
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            logger.warning(f"[ws:{chat_id}] heartbeat send failed (client gone)")
            task.cancel()
            raise


@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int):
    # Try to authenticate from query param
    token = websocket.query_params.get("token")
    uid = None
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            uid = int(payload.get("sub"))
        except Exception:
            pass

    # Gate non-admins when the bot is under maintenance or chat is admin-only.
    try:
        maint = await get_maintenance_mode()
    except Exception:
        maint = False
    try:
        admin_only = await get_chat_admin_only()
    except Exception:
        admin_only = False
    is_admin_user = uid in ADMIN_IDS if uid is not None else False
    if not is_admin_user and (maint or admin_only):
        reason = "maintenance" if maint else "admin_only"
        logger.warning(
            f"[ws:{chat_id}] rejected uid={uid} ({reason}, isAdmin={is_admin_user})"
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "code": reason.upper(),
            "error": (
                "Bot is under maintenance. Please try again later."
                if maint
                else "Chat is currently restricted to admins only."
            ),
        })
        await websocket.close(code=4001 if maint else 4002, reason=reason)
        return

    logger.info(f"[ws:{chat_id}] connect (uid={uid})")
    await ws_manager.connect(websocket, chat_id)
    try:
        # Send agent_connected confirmation with minimal state.
        # behaviorType "think" = conversational mode: the Mini App hides all
        # build-phase UI (blueprint / phases / deploy panels) for this chat.
        await websocket.send_json({
            "type": "agent_connected",
            "state": {"behaviorType": "think", "projectType": "app"},
            "templateDetails": {},
            "previewUrl": None,
        })

        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "user_suggestion":
                user_msg = (data.get("message") or "").strip()
                if not user_msg:
                    continue
                logger.info(f"[ws:{chat_id}] user_suggestion: {user_msg[:80]!r}")

                # Load history BEFORE inserting the new user message so we
                # don't duplicate it in the context window.
                history = await _load_chat_history(chat_id)

                # Persist user message
                await _persist_message(chat_id, "user", user_msg)

                # Build context: system + history + new user message
                llm_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
                llm_messages += history[-20:]
                llm_messages.append({"role": "user", "content": user_msg})

                # Show a thinking indicator while the LLM works.
                try:
                    await websocket.send_json({
                        "type": "conversation_response",
                        "conversationId": "main",
                        "reasoning": {"delta": "Thinking…"},
                        "isStreaming": True,
                    })
                except Exception:
                    pass

                ai_reply = ""
                used_model = None
                try:
                    ai_reply, used_model = await _run_with_heartbeat(
                        _call_llm(llm_messages), websocket, chat_id
                    )
                except Exception as e:
                    logger.exception(f"[ws:{chat_id}] llm task crashed: {e}")

                if not ai_reply:
                    err = used_model or "unknown error"
                    ai_reply = (
                        "⚠️ I couldn't reach my AI backend just now. Please try again in a moment.\n\n"
                        f"`Details: {err[:160]}`"
                    )
                    used_model = None

                # Persist AI message
                await _persist_message(chat_id, "assistant", ai_reply, used_model)

                # Close the reasoning indicator, then stream the reply.
                try:
                    await websocket.send_json({
                        "type": "conversation_response",
                        "conversationId": "main",
                        "reasoning": {"done": True},
                    })
                except Exception:
                    pass

                words = ai_reply.split(" ")
                for i in range(0, len(words), 3):
                    chunk = " ".join(words[i : i + 3]) + " "
                    await websocket.send_json({
                        "type": "conversation_response",
                        "conversationId": "main",
                        "message": chunk,
                        "isStreaming": True,
                    })
                    await asyncio.sleep(0.03)

                # Send final complete message
                await websocket.send_json({
                    "type": "conversation_response",
                    "conversationId": "main",
                    "message": ai_reply,
                    "isStreaming": False,
                })
                logger.info(f"[ws:{chat_id}] replied via {used_model} ({len(ai_reply)} chars)")

            elif msg_type == "clear_conversation":
                logger.info(f"[ws:{chat_id}] clear_conversation")
                try:
                    await run_db(lambda: _exec_db("DELETE FROM messages WHERE chat_id = %s", (chat_id,)))
                except Exception as e:
                    logger.warning(f"[ws:{chat_id}] clear failed: {e}")
                await websocket.send_json({"type": "conversation_cleared"})

            elif msg_type == "get_conversation_state":
                # Return existing messages from DB
                history_rows = []
                try:
                    rows = await run_db(_load_state_rows_sync, chat_id)
                    for row in rows:
                        history_rows.append({
                            "role": row["role"],
                            "content": row["content"],
                            "conversationId": "main",
                        })
                except Exception as e:
                    logger.warning(f"[ws:{chat_id}] state load failed: {e}")
                logger.info(f"[ws:{chat_id}] conversation_state sent ({len(history_rows)} msgs)")
                await websocket.send_json({
                    "type": "conversation_state",
                    "state": {"runningHistory": history_rows, "behaviorType": "think", "projectType": "app"},
                })

            elif msg_type == "generate_all":
                # No server-side code generation yet: acknowledge immediately so
                # the frontend's generating state resolves instead of spinning.
                logger.info(f"[ws:{chat_id}] generate_all ack (no-op)")
                await websocket.send_json({"type": "generation_complete"})

            elif msg_type == "ping":
                pass  # heartbeat from client — no response needed

            else:
                logger.debug(f"[ws:{chat_id}] ignored msg_type={msg_type}")

    except WebSocketDisconnect:
        logger.info(f"[ws:{chat_id}] disconnect")
        ws_manager.disconnect(websocket, chat_id)
    except Exception as e:
        logger.exception(f"[ws:{chat_id}] error: {e}")
        ws_manager.disconnect(websocket, chat_id)


@app.post("/api/auth/telegram")
async def auth_telegram(req: TelegramAuthRequest):
    """Verify Telegram Mini App initData and return JWT + user info."""
    try:
        tg_user = verify_telegram_init_data(req.initData)
    except ValueError as e:
        raise HTTPException(401, str(e))

    telegram_id = tg_user["id"]

    # Create/update user in DB (off event loop)
    def _upsert_user():
        user = db_get_user(telegram_id)
        if not user:
            conn = get_db()
            try:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO users (user_id, username, first_name, last_name, created_at)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET
                           username = EXCLUDED.username,
                           first_name = EXCLUDED.first_name,
                           last_name = EXCLUDED.last_name""",
                    (
                        telegram_id,
                        tg_user.get("username"),
                        tg_user.get("first_name"),
                        tg_user.get("last_name"),
                        datetime.now(timezone.utc),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            user = db_get_user(telegram_id)
        return user

    await run_db(_upsert_user)

    token = create_jwt_token(telegram_id)
    maintenance = await get_maintenance_mode()

    return {
        "token": token,
        "user": {
            "id": telegram_id,
            "username": tg_user.get("username"),
            "first_name": tg_user.get("first_name"),
            "last_name": tg_user.get("last_name"),
        },
        "maintenance": maintenance and telegram_id not in ADMIN_IDS,
        "isAdmin": telegram_id in ADMIN_IDS,
    }


@app.get("/api/user/me")
async def get_me(telegram_id: int = Depends(get_current_user)):
    """Get current user profile."""
    user = await run_db(db_get_user, telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    from database import get_user_usage
    usage = await run_db(get_user_usage, telegram_id)
    
    return {
        "id": telegram_id,
        "username": user.get("username"),
        "firstName": user.get("first_name"),
        "lastName": user.get("last_name"),
        "dailyMessagesUsed": usage["used"],
        "dailyLimit": usage["limit"],
        "remaining": usage["remaining"],
        "resetAt": usage["resetAt"],
    }


@app.get("/api/limits")
async def get_limits(telegram_id: int = Depends(get_current_user)):
    """Get user's daily usage limits (rolling 24h window)."""
    from database import get_user_usage
    usage = await run_db(get_user_usage, telegram_id)
    
    used = usage.get("used", 0)
    limit = usage.get("limit", 10)
    remaining = usage.get("remaining", limit)
    within = used < limit
    
    return {
        "cloudflareConnectEnabled": False,
        "config": {
            "unlimited": False,
            "limit": {
                "type": "daily",
                "maxValue": limit,
                "window": "24h",
            },
        },
        "usage": {
            "prompts": {"used": used, "max": limit, "window": "24h"},
        },
        "limitCheck": {
            "withinLimits": within,
            "exceededLimits": [] if within else [{"type": "prompts", "window": "24h", "current": used, "max": limit, "percentUsed": int(used / limit * 100) if limit else 0}],
            "shouldUseUserKey": False,
            "message": f"{used}/{limit} prompts used" if within else "Daily limit reached",
        },
        "hasUserToken": False,
        "hasCloudflareConfigured": False,
        "aiGatewayConnected": False,
        "aiGatewayEnabled": False,
        "aiGatewayPreferenceExplicit": False,
        "cloudflareCredits": None,
    }


@app.get("/api/projects")
async def list_projects(telegram_id: int = Depends(get_current_user)):
    """List user's projects."""
    def _q():
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """SELECT id, name, prompt, project_type, status, created_at, updated_at
                   FROM projects WHERE user_id = %s ORDER BY updated_at DESC""",
                (telegram_id,),
            )
            return [dict(p) for p in cur.fetchall()]
        finally:
            conn.close()
    projects = await run_db(_q)
    return {"projects": projects}


@app.post("/api/projects")
async def create_project(
    req: ProjectCreateRequest, telegram_id: int = Depends(get_current_user)
):
    """Create a new project."""
    # Auto-detect project type from prompt if not specified
    project_type = req.projectType or "website"

    def _ins():
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """INSERT INTO projects (user_id, name, prompt, project_type, status, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, 'created', NOW(), NOW())
                   RETURNING id, name, prompt, project_type, status, created_at""",
                (telegram_id, req.name, req.prompt, project_type),
            )
            project = dict(cur.fetchone())
            conn.commit()
            return project
        finally:
            conn.close()
    project = await run_db(_ins)
    return {"project": project}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: int, telegram_id: int = Depends(get_current_user)):
    """Get project details."""
    def _q():
        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM projects WHERE id = %s AND user_id = %s",
                (project_id, telegram_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    project = await run_db(_q)
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project": project}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, telegram_id: int = Depends(get_current_user)):
    """Delete a project."""
    def _del():
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM projects WHERE id = %s AND user_id = %s",
                (project_id, telegram_id),
            )
            deleted = cur.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()
    deleted = await run_db(_del)
    if deleted == 0:
        raise HTTPException(404, "Project not found")
    return {"success": True}


@app.post("/api/chat")
async def chat(req: ChatRequest, telegram_id: int = Depends(get_current_user)):
    """Send a message to AI and get a response.

    Uses OpenCode Zen API with model fallbacks.
    """
    # Check daily limit (rolling 24h)
    from database import check_and_increment_usage
    allowed, remaining, reset_at = await run_db(check_and_increment_usage, telegram_id)
    if not allowed:
        raise HTTPException(429, f"Daily message limit reached. Resets at {reset_at}.")

    # Build AI request
    messages = [{"role": "user", "content": req.message}]

    # Shared helper: primary model + fallbacks, fast retries, logging
    reply, model_used = await _call_llm(messages)
    if reply:
        return {
            "response": reply,
            "model": model_used,
            "remaining": remaining,
        }

    raise HTTPException(503, f"AI temporarily unavailable. Last error: {model_used}")


# ==================== CHAT SYSTEM ====================

@app.get("/api/chats")
async def list_chats(telegram_id: int = Depends(get_current_user)):
    """List user's chats with last message preview."""
    from database import get_user_chats
    chats = await run_db(get_user_chats, telegram_id)
    return {"chats": chats}


@app.post("/api/chats")
async def create_chat(req: ChatCreateRequest, telegram_id: int = Depends(get_current_user)):
    """Create a new chat."""
    from database import create_chat as db_create_chat
    chat = await run_db(db_create_chat, telegram_id, req.title)
    return {"chat": chat}


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: int, telegram_id: int = Depends(get_current_user)):
    """Get a chat with its messages."""
    from database import get_chat as db_get_chat, get_chat_messages
    chat = await run_db(db_get_chat, chat_id, telegram_id)
    if not chat:
        raise HTTPException(404, "Chat not found")
    messages = await run_db(get_chat_messages, chat_id)
    return {"chat": chat, "messages": messages}


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: int, telegram_id: int = Depends(get_current_user)):
    """Delete a chat and its messages."""
    from database import delete_chat
    deleted = await run_db(delete_chat, chat_id, telegram_id)
    if not deleted:
        raise HTTPException(404, "Chat not found")
    return {"success": True}


@app.put("/api/chats/{chat_id}/rename")
async def rename_chat(chat_id: int, req: ChatRenameRequest, telegram_id: int = Depends(get_current_user)):
    """Rename a chat."""
    from database import rename_chat
    updated = await run_db(rename_chat, chat_id, telegram_id, req.title)
    if not updated:
        raise HTTPException(404, "Chat not found")
    return {"success": True}


@app.post("/api/chats/{chat_id}/messages")
async def send_chat_message(chat_id: int, req: ChatMessageRequest, telegram_id: int = Depends(get_current_user)):
    """Send a message in a chat and get AI response with context."""
    from database import get_chat as db_get_chat, get_chat_messages, add_message
    from database import check_and_increment_usage

    # Verify chat exists and belongs to user
    chat = await run_db(db_get_chat, chat_id, telegram_id)
    if not chat:
        raise HTTPException(404, "Chat not found")

    # Check daily limit
    allowed, remaining, reset_at = await run_db(check_and_increment_usage, telegram_id)
    if not allowed:
        raise HTTPException(429, f"Daily message limit reached. Resets at {reset_at}.")

    # Save user message
    await run_db(add_message, chat_id, "user", req.message)

    # Load context (last 20 messages)
    context = await run_db(get_chat_messages, chat_id, 20)

    # Build messages array for AI
    system_msg = {
        "role": "system",
        "content": "You are OXYCODE AI, an intelligent coding assistant. Help users build websites, bots, and apps. Be concise, helpful, and provide working code. When generating code, use proper formatting with markdown code blocks."
    }
    ai_messages = [system_msg] + [
        {"role": m["role"], "content": m["content"]}
        for m in context
    ]

    # Try AI with shared model-fallback helper (fast retries + logging)
    reply, model_used = await _call_llm(ai_messages)
    if reply:
        await run_db(add_message, chat_id, "assistant", reply, model_used)
        return {
            "response": reply,
            "model": model_used,
            "remaining": remaining,
        }

    raise HTTPException(503, f"AI temporarily unavailable. Last error: {model_used}")


# ==================== CLOUDFLARE OAUTH ====================

@app.get("/api/cloudflare/status")
async def cloudflare_status(telegram_id: int = Depends(get_current_user)):
    """Check if user has a connected Cloudflare account."""
    from cloudflare_oauth import get_cloudflare_account, is_cloudflare_connected
    
    connected = is_cloudflare_connected(telegram_id)
    account = get_cloudflare_account(telegram_id) if connected else None
    
    return {
        "connected": connected,
        "account": {
            "accountId": account.get("account_id"),
            "accountName": account.get("account_name"),
            "email": account.get("email"),
            "connectedAt": account.get("connected_at").isoformat() if account and account.get("connected_at") else None,
        } if account else None,
    }


@app.get("/api/cloudflare/auth-url")
async def cloudflare_auth_url(telegram_id: int = Depends(get_current_user)):
    """Generate Cloudflare OAuth authorization URL."""
    from cloudflare_oauth import generate_auth_url
    import secrets
    
    # Generate state with user ID embedded for callback
    state_data = f"{telegram_id}:{secrets.token_urlsafe(16)}"
    state = state_data
    
    try:
        url = generate_auth_url(state)
        return {"url": url, "state": state}
    except ValueError as e:
        raise HTTPException(500, str(e))


@app.get("/api/cloudflare/callback")
async def cloudflare_callback(code: str = None, state: str = None):
    """Handle Cloudflare OAuth callback.
    
    This endpoint is called by Cloudflare after user authorizes.
    It exchanges the code for a token and saves it.
    """
    from cloudflare_oauth import (
        exchange_code_for_token,
        verify_token,
        get_cloudflare_accounts,
        save_cloudflare_account,
    )
    
    if not code:
        raise HTTPException(400, "Missing authorization code")
    
    if not state:
        raise HTTPException(400, "Missing state parameter")
    
    # Extract user ID from state
    try:
        telegram_id = int(state.split(":")[0])
    except (ValueError, IndexError):
        raise HTTPException(400, "Invalid state parameter")
    
    # Exchange code for token
    try:
        token_data = await exchange_code_for_token(code)
    except ValueError as e:
        raise HTTPException(400, f"Token exchange failed: {e}")
    
    api_token = token_data.get("access_token")
    if not api_token:
        raise HTTPException(400, "No access token received")
    
    # Verify token and get user info
    user_info = await verify_token(api_token)
    if user_info.get("status") != "active":
        raise HTTPException(400, "Token verification failed")
    
    # Get accounts
    accounts = await get_cloudflare_accounts(api_token)
    account = accounts[0] if accounts else None
    
    # Save to database
    save_cloudflare_account(
        telegram_id=telegram_id,
        api_token=api_token,
        account_id=account["id"] if account else None,
        account_name=account["name"] if account else None,
        email=user_info.get("email"),
    )
    
    # Return success (this will be opened in a popup/close tab)
    return {
        "success": True,
        "message": "Cloudflare account connected successfully!",
        "accountName": account["name"] if account else None,
        "email": user_info.get("email"),
    }


@app.delete("/api/cloudflare/disconnect")
async def cloudflare_disconnect(telegram_id: int = Depends(get_current_user)):
    """Disconnect Cloudflare account."""
    from cloudflare_oauth import remove_cloudflare_account
    
    removed = remove_cloudflare_account(telegram_id)
    if not removed:
        raise HTTPException(404, "No Cloudflare account connected")
    
    return {"success": True, "message": "Cloudflare account disconnected"}


@app.get("/cloudflare-callback", response_class=HTMLResponse)
async def cloudflare_callback_page():
    """Serve the Cloudflare OAuth callback HTML page."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "cloudflare_callback.html")
    try:
        with open(template_path, "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Callback page not found</h1>", status_code=404)


# ==================== DEPLOYMENT ====================

class DeployRequest(BaseModel):
    projectId: int
    projectName: str
    files: dict  # {filepath: content}
    deployType: str = "pages"  # "pages" or "workers"


@app.post("/api/deploy")
async def deploy_project(req: DeployRequest, telegram_id: int = Depends(get_current_user)):
    """Deploy a project to Cloudflare Pages or Workers."""
    from cloudflare_deploy import deploy_to_pages, deploy_to_workers, generate_worker_script
    from cloudflare_oauth import is_cloudflare_connected
    
    if not is_cloudflare_connected(telegram_id):
        raise HTTPException(400, "Cloudflare account not connected. Please connect first.")
    
    try:
        if req.deployType == "workers":
            # Generate Worker script from HTML
            html = req.files.get("index.html", "")
            js = req.files.get("script.js", "")
            css = req.files.get("style.css", "")
            worker_script = generate_worker_script(html, js, css)
            result = await deploy_to_workers(
                telegram_id=telegram_id,
                script_name=req.projectName,
                script_content=worker_script,
            )
        else:
            # Deploy to Pages
            result = await deploy_to_pages(
                telegram_id=telegram_id,
                project_name=req.projectName,
                files=req.files,
            )
        
        # Update project status in DB
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE projects SET status = 'deployed', updated_at = NOW() WHERE id = %s AND user_id = %s",
            (req.projectId, telegram_id),
        )
        conn.commit()
        conn.close()
        
        return result
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        raise HTTPException(500, f"Deployment failed: {str(e)}")


@app.get("/api/deployments")
async def list_deployments(telegram_id: int = Depends(get_current_user)):
    """List user's deployed projects."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT id, name, status, project_type, created_at, updated_at
           FROM projects WHERE user_id = %s AND status = 'deployed'
           ORDER BY updated_at DESC""",
        (telegram_id,),
    )
    projects = [dict(p) for p in cur.fetchall()]
    conn.close()
    return {"deployments": projects}


# ==================== ERROR/FIX SYSTEM ====================

class FixRequest(BaseModel):
    projectId: int
    errorType: str
    errorMessage: str
    url: Optional[str] = None
    stackTrace: Optional[str] = None
    files: dict  # {filepath: content}


@app.post("/api/fix")
async def fix_error(req: FixRequest, telegram_id: int = Depends(get_current_user)):
    """Analyze an error and suggest a fix using AI."""
    from error_fix import analyze_error, detect_error_type
    
    # Auto-detect error type if not specified
    error_type = req.errorType or detect_error_type(req.errorMessage)
    
    # Analyze the error
    result = await analyze_error(
        error_type=error_type,
        error_message=req.errorMessage,
        project_files=req.files,
        url=req.url,
        stack_trace=req.stackTrace,
    )
    
    return {
        "analysis": result["analysis"],
        "fixes": result["fixes"],
        "autoFixable": result["autoFixable"],
        "errorType": error_type,
    }


class AutoFixRequest(BaseModel):
    projectId: int
    projectName: str
    fixes: list  # [{"file": str, "content": str}]
    deployType: str = "pages"


@app.post("/api/fix/apply")
async def apply_fix(req: AutoFixRequest, telegram_id: int = Depends(get_current_user)):
    """Apply AI-generated fixes and re-deploy."""
    from cloudflare_deploy import deploy_to_pages, deploy_to_workers, generate_worker_script
    from cloudflare_oauth import is_cloudflare_connected
    
    if not is_cloudflare_connected(telegram_id):
        raise HTTPException(400, "Cloudflare account not connected")
    
    if not req.fixes:
        raise HTTPException(400, "No fixes to apply")
    
    # Build files dict from fixes
    files = {fix["file"]: fix["content"] for fix in req.fixes}
    
    try:
        if req.deployType == "workers":
            html = files.get("index.html", "")
            js = files.get("script.js", "")
            css = files.get("style.css", "")
            worker_script = generate_worker_script(html, js, css)
            result = await deploy_to_workers(
                telegram_id=telegram_id,
                script_name=req.projectName,
                script_content=worker_script,
            )
        else:
            result = await deploy_to_pages(
                telegram_id=telegram_id,
                project_name=req.projectName,
                files=files,
            )
        
        # Update project status
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE projects SET status = 'deployed', updated_at = NOW() WHERE id = %s AND user_id = %s",
            (req.projectId, telegram_id),
        )
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "Fix applied and re-deployed successfully!",
            "url": result.get("url"),
        }
        
    except Exception as e:
        logger.error(f"Auto-fix deployment failed: {e}")
        raise HTTPException(500, f"Fix deployment failed: {str(e)}")


@app.post("/api/admin/maintenance/toggle")
async def toggle_maintenance(telegram_id: int = Depends(get_current_user)):
    """Admin-only: toggle maintenance mode."""
    if telegram_id not in ADMIN_IDS:
        raise HTTPException(403, "Admin access required")
    from database import toggle_maintenance as db_toggle
    new_state = await run_db(db_toggle)
    bust_maintenance_cache()
    logger.info(f"[admin:{telegram_id}] maintenance toggled -> {new_state}")
    return {"maintenance": new_state, "message": f"Maintenance {'ON' if new_state else 'OFF'}"}


@app.post("/api/admin/chat-access/toggle")
async def toggle_chat_access(telegram_id: int = Depends(get_current_user)):
    """Admin-only: toggle admin-only chat restriction (independent of maintenance)."""
    if telegram_id not in ADMIN_IDS:
        raise HTTPException(403, "Admin access required")
    from database import toggle_chat_admin_only as db_toggle
    new_state = await run_db(db_toggle)
    bust_chat_admin_only_cache()
    logger.info(f"[admin:{telegram_id}] chat admin_only toggled -> {new_state}")
    return {
        "chatAdminOnly": new_state,
        "message": f"Chat restricted to admins {'ON' if new_state else 'OFF'}",
    }


@app.get("/api/admin/chat-access")
async def get_chat_access(telegram_id: int = Depends(get_current_user)):
    """Admin-only: read current chat access flags."""
    if telegram_id not in ADMIN_IDS:
        raise HTTPException(403, "Admin access required")
    return {
        "chatAdminOnly": await get_chat_admin_only(),
        "maintenance": await get_maintenance_mode(),
    }


# ==================== STARTUP ====================

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    # Verify database connection
    if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL missing or not a Postgres URL")

    uvicorn.run(app, host="0.0.0.0", port=8000)
