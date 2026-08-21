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

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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

OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/v1"
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
        if path in ("/api/health", "/docs", "/openapi.json") or path.startswith("/static"):
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


# ==================== ROUTES ====================

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "oxycode-ai-backend"}


@app.post("/api/auth/telegram")
async def auth_telegram(req: TelegramAuthRequest):
    """Verify Telegram Mini App initData and return JWT + user info."""
    try:
        tg_user = verify_telegram_init_data(req.initData)
    except ValueError as e:
        raise HTTPException(401, str(e))

    telegram_id = tg_user["id"]

    # Admin-only restriction
    if telegram_id not in ADMIN_IDS:
        raise HTTPException(403, "Access denied. This bot is in private beta.")

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
            "firstName": tg_user.get("first_name"),
            "lastName": tg_user.get("last_name"),
        },
    }


@app.get("/api/user/me")
async def get_me(telegram_id: int = Depends(get_current_user)):
    """Get current user profile."""
    user = db_get_user(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    msg_count = db_get_user_msg_count(telegram_id, today)

    return {
        "id": telegram_id,
        "username": user.get("username"),
        "firstName": user.get("first_name"),
        "lastName": user.get("last_name"),
        "dailyMessagesUsed": msg_count,
        "dailyLimit": FREE_DAILY_LIMIT,
    }


@app.get("/api/limits")
async def get_limits(telegram_id: int = Depends(get_current_user)):
    """Get user's daily usage limits."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    msg_count = db_get_user_msg_count(telegram_id, today)
    remaining = max(0, FREE_DAILY_LIMIT - msg_count)

    return {
        "dailyLimit": FREE_DAILY_LIMIT,
        "usedToday": msg_count,
        "remaining": remaining,
        "resetsAt": (datetime.now(timezone.utc) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat(),
    }


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
    # Check daily limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    msg_count = db_get_user_msg_count(telegram_id, today)
    if msg_count >= FREE_DAILY_LIMIT:
        raise HTTPException(429, "Daily message limit reached. Resets at midnight UTC.")

    # Increment message count
    db_increment_msg_count(telegram_id, today)

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
                                "remaining": FREE_DAILY_LIMIT - msg_count - 1,
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
