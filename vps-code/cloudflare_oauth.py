"""
OXYCODE AI — Cloudflare OAuth Integration
==========================================

Handles per-user Cloudflare account connection via OAuth.
Each user connects their own Cloudflare account for deploying
their projects to Cloudflare Pages and Workers.

OAuth Flow:
1. User clicks "Connect Cloudflare" in Mini App
2. Redirected to Cloudflare OAuth authorization page
3. User authorizes the app
4. Cloudflare redirects back with authorization code
5. We exchange code for API token
6. Token saved to database, associated with user

Cloudflare API Token Scopes Needed:
- Workers Scripts: Edit
- Workers KV Storage: Edit
- Workers R2 Storage: Edit
- Cloudflare Pages: Edit
- Zone Settings: Read
- DNS: Read/Write (for custom domains)
"""

import os
import hashlib
import secrets
import time
import aiohttp
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# ==================== CONFIG ====================

# Cloudflare OAuth App credentials (create at https://dash.cloudflare.com/profile/api-tokens)
# For local dev, create a Cloudflare OAuth App and set these in .env
CLOUDFLARE_CLIENT_ID = os.getenv("CLOUDFLARE_CLIENT_ID", "")
CLOUDFLARE_CLIENT_SECRET = os.getenv("CLOUDFLARE_CLIENT_SECRET", "")

# Where Cloudflare redirects after auth
# In production, this should be your VPS domain
CLOUDFLARE_REDIRECT_URI = os.getenv(
    "CLOUDFLARE_REDIRECT_URI",
    "https://153.75.247.105:8000/cloudflare-callback"
)

# Cloudflare OAuth endpoints
CLOUDFLARE_AUTH_URL = "https://dash.cloudflare.com/oauth2/auth"
CLOUDFLARE_TOKEN_URL = "https://api.cloudflare.com/client/v4/user/tokens/verify"
CLOUDFLARE_TOKEN_EXCHANGE_URL = "https://dash.cloudflare.com/oauth2/token"

# Required OAuth scopes for Cloudflare
CLOUDFLARE_SCOPES = [
    "user:read",
    "workers:write",
    "pages:write",
    "kv_storage:write",
    "r2_storage:write",
    "dns:read",
    "zone:read",
]

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ==================== DATABASE ====================

def get_db():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def _ensure_table():
    """Ensure cloudflare_accounts table exists."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cloudflare_accounts (
            user_id BIGINT PRIMARY KEY,
            api_token TEXT NOT NULL,
            account_id TEXT,
            account_name TEXT,
            email TEXT,
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


# Call on module load
try:
    _ensure_table()
except Exception as e:
    logger.warning(f"Could not create cloudflare_accounts table: {e}")


# ==================== OAUTH FLOW ====================

def generate_auth_url(state: str = None) -> str:
    """Generate Cloudflare OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Full authorization URL to redirect user to
    """
    if not CLOUDFLARE_CLIENT_ID:
        raise ValueError("CLOUDFLARE_CLIENT_ID not configured")

    if not state:
        state = secrets.token_urlsafe(32)

    params = {
        "client_id": CLOUDFLARE_CLIENT_ID,
        "redirect_uri": CLOUDFLARE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(CLOUDFLARE_SCOPES),
        "state": state,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{CLOUDFLARE_AUTH_URL}?{query_string}"


async def exchange_code_for_token(code: str) -> Dict:
    """Exchange authorization code for API token.

    Returns:
        {
            "access_token": str,
            "expires_in": int,
            "refresh_expires_in": int,
            "token_type": str,
            "scope": str,
        }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            CLOUDFLARE_TOKEN_EXCHANGE_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": CLOUDFLARE_CLIENT_ID,
                "client_secret": CLOUDFLARE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": CLOUDFLARE_REDIRECT_URI,
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise ValueError(f"Token exchange failed: HTTP {resp.status} - {body[:200]}")
            return await resp.json()


async def verify_token(api_token: str) -> Dict:
    """Verify an API token and get user info.

    Returns:
        {
            "id": str,
            "status": "active" | "expired" | "invalid",
            "email": str,
            ...
        }
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            CLOUDFLARE_TOKEN_URL,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                return {"status": "invalid"}
            data = await resp.json()
            if data.get("success"):
                result = data.get("result", {})
                return {
                    "id": result.get("id"),
                    "status": result.get("status"),
                    "email": result.get("email"),
                    "name": result.get("name"),
                    "policies": result.get("policies", []),
                }
            return {"status": "invalid"}


async def get_cloudflare_accounts(api_token: str) -> list:
    """Get Cloudflare accounts accessible with this token.

    Returns list of accounts with id and name.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.cloudflare.com/client/v4/accounts",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            if data.get("success"):
                return [
                    {"id": acc["id"], "name": acc["name"]}
                    for acc in data.get("result", [])
                ]
            return []


# ==================== SAVE / LOAD / DELETE ====================

def save_cloudflare_account(
    telegram_id: int,
    api_token: str,
    account_id: str = None,
    account_name: str = None,
    email: str = None,
):
    """Save Cloudflare account credentials for a user."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO cloudflare_accounts (user_id, api_token, account_id, account_name, email, connected_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            api_token = EXCLUDED.api_token,
            account_id = EXCLUDED.account_id,
            account_name = EXCLUDED.account_name,
            email = EXCLUDED.email,
            updated_at = EXCLUDED.updated_at
    ''', (telegram_id, api_token, account_id, account_name, email, datetime.now(timezone.utc), datetime.now(timezone.utc)))
    conn.commit()
    conn.close()
    logger.info(f"Saved Cloudflare account for user {telegram_id}")


def get_cloudflare_account(telegram_id: int) -> Optional[Dict]:
    """Get saved Cloudflare account for a user."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM cloudflare_accounts WHERE user_id = %s",
        (telegram_id,),
    )
    account = cur.fetchone()
    conn.close()
    return dict(account) if account else None


def remove_cloudflare_account(telegram_id: int) -> bool:
    """Remove (disconnect) Cloudflare account for a user."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cloudflare_accounts WHERE user_id = %s", (telegram_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def is_cloudflare_connected(telegram_id: int) -> bool:
    """Check if user has a connected Cloudflare account."""
    account = get_cloudflare_account(telegram_id)
    return account is not None


# ==================== API HELPERS ====================

async def cf_api_get(telegram_id: int, endpoint: str) -> Dict:
    """Make an authenticated GET request to Cloudflare API.

    Args:
        telegram_id: User's Telegram ID (to get their token)
        endpoint: API endpoint path (e.g., "/accounts/abc123/pages/projects")

    Returns:
        Cloudflare API response dict
    """
    account = get_cloudflare_account(telegram_id)
    if not account:
        raise ValueError("Cloudflare account not connected")

    api_token = account["api_token"]
    url = f"https://api.cloudflare.com/client/v4{endpoint}"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            return await resp.json()


async def cf_api_post(telegram_id: int, endpoint: str, data: Dict = None) -> Dict:
    """Make an authenticated POST request to Cloudflare API."""
    account = get_cloudflare_account(telegram_id)
    if not account:
        raise ValueError("Cloudflare account not connected")

    api_token = account["api_token"]
    url = f"https://api.cloudflare.com/client/v4{endpoint}"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json=data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            return await resp.json()


async def cf_api_put(telegram_id: int, endpoint: str, data: Dict = None) -> Dict:
    """Make an authenticated PUT request to Cloudflare API."""
    account = get_cloudflare_account(telegram_id)
    if not account:
        raise ValueError("Cloudflare account not connected")

    api_token = account["api_token"]
    url = f"https://api.cloudflare.com/client/v4{endpoint}"

    async with aiohttp.ClientSession() as session:
        async with session.put(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json=data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            return await resp.json()
