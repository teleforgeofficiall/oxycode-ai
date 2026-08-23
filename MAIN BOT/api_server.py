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

# ==================== CONFIG ====================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
JWT_SECRET = os.getenv("JWT_SECRET", "oxycode-miniapp-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 7 * 24  # 7 days

OPENCODE_ZEN_BASE_URL = "https://opencode.ai/inference/openai/v1"
OPENCODE_ZEN_MODEL = os.getenv("OPENCODE_ZEN_MODEL", "mimo-v2.5-free")
OPENCODE_ZEN_FALLBACKS = os.getenv(
    "OPENCODE_ZEN_FALLBACKS",
    "deepseek-v4-flash-free,hy3-free,nemotron-3.5-lightning-free,nemotron-3-ultra-free,laguna-s-2.1-free"
).split(",")

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
    payload = {
        "sub": str(telegram_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
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
        
        # Check maintenance mode
        try:
            maintenance = db_is_maintenance_mode()
        except Exception:
            maintenance = False
        
        if not maintenance:
            return await call_next(request)
        
        # Maintenance is ON — only allow admins
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                telegram_id = int(payload["sub"])
                if telegram_id in ADMIN_IDS:
                    return await call_next(request)
            except Exception:
                pass
        
        # Non-admin or no token — block
        return JSONResponse(
            status_code=503,
            content={
                "error": "maintenance",
                "message": "Bot is under maintenance. Please try again later.",
            },
        )


app.add_middleware(MaintenanceMiddleware)


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
    return {"maintenance": db_is_maintenance_mode()}


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

    # Create chat in database
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "INSERT INTO chats (user_id, title) VALUES (%s, %s) RETURNING id, title, created_at, updated_at",
            (telegram_id, query[:100] if query else "New Chat"),
        )
        chat = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()

    chat_id = chat["id"]

    # Return NDJSON stream
    async def stream():
        yield json.dumps({"template": {"files": []}}) + "\n"
        yield json.dumps({"behaviorType": behavior_type}) + "\n"
        yield json.dumps({"projectType": project_type}) + "\n"
        yield json.dumps({"agentId": str(chat_id)}) + "\n"
        yield json.dumps({"websocketUrl": f"ws://153.75.247.105:8000/ws/{chat_id}"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


# ==================== WEBSOCKET ENDPOINT ====================

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

    await ws_manager.connect(websocket, chat_id)
    try:
        # Send agent_connected confirmation with minimal state
        await websocket.send_json({
            "type": "agent_connected",
            "state": {"behaviorType": "phasic", "projectType": "app"},
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
                user_msg = data.get("message", "")
                # Persist user message
                try:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO messages (chat_id, role, content) VALUES (%s, 'user', %s)",
                        (chat_id, user_msg),
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

                # Generate AI response
                ai_reply = ""
                try:
                    models = [OPENCODE_ZEN_MODEL] + [m for m in OPENCODE_ZEN_FALLBACKS if m != OPENCODE_ZEN_MODEL]
                    last_err = ""
                    async with aiohttp.ClientSession() as http:
                        for model in models:
                            payload = {"model": model, "messages": [{"role": "user", "content": user_msg}], "stream": False}
                            for attempt in range(3):
                                try:
                                    async with http.post(
                                        f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                                        headers={"Content-Type": "application/json", "User-Agent": "opencode/1.18.16"},
                                        json=payload,
                                        timeout=aiohttp.ClientTimeout(total=60),
                                    ) as resp:
                                        if resp.status == 200:
                                            result = await resp.json()
                                            ai_reply = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                                            break
                                        body = await resp.text()
                                        last_err = f"HTTP {resp.status}: {body[:120]}"
                                        if resp.status in (429, 500, 502, 503, 504) and attempt < 2:
                                            await asyncio.sleep(2.0 * (attempt + 1))
                                            continue
                                        break
                                except Exception as e:
                                    last_err = f"{type(e).__name__}: {str(e)[:120]}"
                                    if attempt < 2:
                                        await asyncio.sleep(2.0 * (attempt + 1))
                                        continue
                                    break
                            if ai_reply:
                                break
                    if not ai_reply:
                        ai_reply = f"AI temporarily unavailable. Last error: {last_err}"
                except Exception as e:
                    ai_reply = f"AI error: {str(e)}"

                # Persist AI message
                try:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO messages (chat_id, role, content) VALUES (%s, 'assistant', %s)",
                        (chat_id, ai_reply),
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

                # Stream response word by word
                words = ai_reply.split(" ")
                for i in range(0, len(words), 3):
                    chunk = " ".join(words[i : i + 3]) + " "
                    await websocket.send_json({
                        "type": "conversation_response",
                        "conversationId": "main",
                        "message": chunk,
                        "isStreaming": True,
                    })
                    await asyncio.sleep(0.05)

                # Send final complete message
                await websocket.send_json({
                    "type": "conversation_response",
                    "conversationId": "main",
                    "message": ai_reply,
                    "isStreaming": False,
                })

            elif msg_type == "clear_conversation":
                try:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM messages WHERE chat_id = %s", (chat_id,))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
                await websocket.send_json({"type": "conversation_cleared"})

            elif msg_type == "get_conversation_state":
                # Return existing messages from DB
                history = []
                try:
                    conn = get_db()
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cur.execute(
                        "SELECT role, content, created_at FROM messages WHERE chat_id = %s ORDER BY created_at",
                        (chat_id,),
                    )
                    rows = cur.fetchall()
                    conn.close()
                    for row in rows:
                        history.append({
                            "role": row["role"],
                            "content": row["content"],
                            "conversationId": "main",
                        })
                except Exception:
                    pass
                await websocket.send_json({
                    "type": "conversation_state",
                    "state": {"runningHistory": history, "behaviorType": "phasic", "projectType": "app"},
                })

            elif msg_type == "generate_all":
                # For new chats, send generation_complete so frontend stops loading
                await websocket.send_json({"type": "generation_complete"})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, chat_id)
    except Exception:
        ws_manager.disconnect(websocket, chat_id)


@app.post("/api/auth/telegram")
async def auth_telegram(req: TelegramAuthRequest):
    """Verify Telegram Mini App initData and return JWT + user info."""
    try:
        tg_user = verify_telegram_init_data(req.initData)
    except ValueError as e:
        raise HTTPException(401, str(e))

    telegram_id = tg_user["id"]

    # Create/update user in DB
    db_user = db_get_user(telegram_id)
    if not db_user:
        # New user — insert
        conn = get_db()
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
        conn.close()
        db_user = db_get_user(telegram_id)

    token = create_jwt_token(telegram_id)

    return {
        "token": token,
        "user": {
            "id": telegram_id,
            "username": tg_user.get("username"),
            "first_name": tg_user.get("first_name"),
            "last_name": tg_user.get("last_name"),
        },
        "maintenance": db_is_maintenance_mode() and telegram_id not in ADMIN_IDS,
        "isAdmin": telegram_id in ADMIN_IDS,
    }


@app.get("/api/user/me")
async def get_me(telegram_id: int = Depends(get_current_user)):
    """Get current user profile."""
    user = db_get_user(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    from database import get_user_usage
    usage = get_user_usage(telegram_id)
    
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
    usage = get_user_usage(telegram_id)
    return usage


@app.get("/api/projects")
async def list_projects(telegram_id: int = Depends(get_current_user)):
    """List user's projects."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT id, name, prompt, project_type, status, created_at, updated_at
           FROM projects WHERE user_id = %s ORDER BY updated_at DESC""",
        (telegram_id,),
    )
    projects = [dict(p) for p in cur.fetchall()]
    conn.close()
    return {"projects": projects}


@app.post("/api/projects")
async def create_project(
    req: ProjectCreateRequest, telegram_id: int = Depends(get_current_user)
):
    """Create a new project."""
    # Auto-detect project type from prompt if not specified
    project_type = req.projectType or "website"

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """INSERT INTO projects (user_id, name, prompt, project_type, status, created_at, updated_at)
           VALUES (%s, %s, %s, %s, 'created', NOW(), NOW())
           RETURNING id, name, prompt, project_type, status, created_at""",
        (telegram_id, req.name, req.prompt, project_type),
    )
    project = dict(cur.fetchone())
    conn.commit()
    conn.close()
    return {"project": project}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: int, telegram_id: int = Depends(get_current_user)):
    """Get project details."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM projects WHERE id = %s AND user_id = %s",
        (project_id, telegram_id),
    )
    project = cur.fetchone()
    conn.close()
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project": dict(project)}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, telegram_id: int = Depends(get_current_user)):
    """Delete a project."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM projects WHERE id = %s AND user_id = %s",
        (project_id, telegram_id),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
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
    allowed, remaining, reset_at = check_and_increment_usage(telegram_id)
    if not allowed:
        raise HTTPException(429, f"Daily message limit reached. Resets at {reset_at}.")

    # Build AI request
    messages = [{"role": "user", "content": req.message}]
    payload = {"model": OPENCODE_ZEN_MODEL, "messages": messages, "stream": False}

    # Try primary model, then fallbacks
    models = [OPENCODE_ZEN_MODEL] + [
        m for m in OPENCODE_ZEN_FALLBACKS if m != OPENCODE_ZEN_MODEL
    ]
    last_err = ""

    async with aiohttp.ClientSession() as session:
        for model in models:
            payload["model"] = model
            for attempt in range(3):
                try:
                    async with session.post(
                        f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            content = (
                                result.get("choices", [{}])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                            return {
                                "response": content,
                                "model": model,
                                "remaining": remaining,
                            }
                        body = await resp.text()
                        last_err = f"HTTP {resp.status}: {body[:120]}"
                        if resp.status in (429, 500, 502, 503, 504) and attempt < 2:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        break
                except Exception as e:
                    last_err = f"{type(e).__name__}: {str(e)[:120]}"
                    if attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    break

    raise HTTPException(503, f"AI temporarily unavailable. Last error: {last_err}")


# ==================== CHAT SYSTEM ====================

@app.get("/api/chats")
async def list_chats(telegram_id: int = Depends(get_current_user)):
    """List user's chats with last message preview."""
    from database import get_user_chats
    chats = get_user_chats(telegram_id)
    return {"chats": chats}


@app.post("/api/chats")
async def create_chat(req: ChatCreateRequest, telegram_id: int = Depends(get_current_user)):
    """Create a new chat."""
    from database import create_chat as db_create_chat
    chat = db_create_chat(telegram_id, req.title)
    return {"chat": chat}


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: int, telegram_id: int = Depends(get_current_user)):
    """Get a chat with its messages."""
    from database import get_chat, get_chat_messages
    chat = get_chat(chat_id, telegram_id)
    if not chat:
        raise HTTPException(404, "Chat not found")
    messages = get_chat_messages(chat_id)
    return {"chat": chat, "messages": messages}


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: int, telegram_id: int = Depends(get_current_user)):
    """Delete a chat and its messages."""
    from database import delete_chat
    deleted = delete_chat(chat_id, telegram_id)
    if not deleted:
        raise HTTPException(404, "Chat not found")
    return {"success": True}


@app.put("/api/chats/{chat_id}/rename")
async def rename_chat(chat_id: int, req: ChatRenameRequest, telegram_id: int = Depends(get_current_user)):
    """Rename a chat."""
    from database import rename_chat
    updated = rename_chat(chat_id, telegram_id, req.title)
    if not updated:
        raise HTTPException(404, "Chat not found")
    return {"success": True}


@app.post("/api/chats/{chat_id}/messages")
async def send_chat_message(chat_id: int, req: ChatMessageRequest, telegram_id: int = Depends(get_current_user)):
    """Send a message in a chat and get AI response with context."""
    from database import get_chat, get_chat_messages, add_message, create_chat
    from database import check_and_increment_usage

    # Verify chat exists and belongs to user
    chat = get_chat(chat_id, telegram_id)
    if not chat:
        raise HTTPException(404, "Chat not found")

    # Check daily limit
    allowed, remaining, reset_at = check_and_increment_usage(telegram_id)
    if not allowed:
        raise HTTPException(429, f"Daily message limit reached. Resets at {reset_at}.")

    # Save user message
    add_message(chat_id, "user", req.message)

    # Load context (last 20 messages)
    context = get_chat_messages(chat_id, limit=20)

    # Build messages array for AI
    system_msg = {
        "role": "system",
        "content": "You are OXYCODE AI, an intelligent coding assistant. Help users build websites, bots, and apps. Be concise, helpful, and provide working code. When generating code, use proper formatting with markdown code blocks."
    }
    ai_messages = [system_msg] + [
        {"role": m["role"], "content": m["content"]}
        for m in context
    ]

    # Try AI with model fallback
    import aiohttp, asyncio
    from config import OPENCODE_ZEN_BASE_URL, OPENCODE_ZEN_MODEL, OPENCODE_ZEN_FALLBACKS

    models = [OPENCODE_ZEN_MODEL] + [m for m in OPENCODE_ZEN_FALLBACKS if m != OPENCODE_ZEN_MODEL]
    last_err = ""

    async with aiohttp.ClientSession() as session:
        for model in models:
            payload = {"model": model, "messages": ai_messages, "stream": False}
            for attempt in range(3):
                try:
                    async with session.post(
                        f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            content = (
                                result.get("choices", [{}])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                            # Save assistant message
                            add_message(chat_id, "assistant", content, model)
                            return {
                                "response": content,
                                "model": model,
                                "remaining": remaining,
                            }
                        body = await resp.text()
                        last_err = f"HTTP {resp.status}: {body[:120]}"
                        if resp.status in (429, 500, 502, 503, 504) and attempt < 2:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        break
                except Exception as e:
                    last_err = f"{type(e).__name__}: {str(e)[:120]}"
                    if attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    break

    raise HTTPException(503, f"AI temporarily unavailable. Last error: {last_err}")


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
        raise HTTPException(403, "Admin only")
    from database import toggle_maintenance as db_toggle
    new_state = db_toggle()
    return {"maintenance": new_state, "message": f"Maintenance {'ON' if new_state else 'OFF'}"}


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
