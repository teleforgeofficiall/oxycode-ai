"""
OXYGENT — Database Layer
========================

PostgreSQL (Neon DB) database operations for the OXYGENT Telegram bot.

This module provides:
    - Connection pooling for efficient Neon DB connections
    - Schema isolation for staging/clone deployments
    - User management (CRUD, bans, voice preferences)
    - Session management for code creation
    - Referral system tracking
    - Payment transaction logging
    - Force-join channel management
    - Admin settings and statistics
    - Daily message limit enforcement

Tables:
    - users: User accounts, settings, and limits
    - channels: Force-join Telegram channels
    - user_states: Conversation flow states
    - code_sessions: Code creation sessions
    - payments: Telegram Stars transactions
    - broadcasts: Broadcast message log
    - settings: Admin-configurable settings

Connection Pool:
    Uses psycopg2 SimpleConnectionPool (5-50 connections) to avoid
    the ~500ms TLS handshake cost on every database call. Includes
    automatic connection validation and fallback to direct connections.

Safety:
    - Refuses to start without valid PostgreSQL URL (prevents SQLite fallback)
    - Production integrity check prevents schema leaks
    - All user_id columns are BIGINT (Telegram IDs are 64-bit)

Author: OXYCODE TEAM
"""

import psycopg2
import psycopg2.extras
from psycopg2 import pool as _psy_pool
from datetime import datetime
from config import DATABASE_URL
import json
import time
import os


# --- Permanent-storage guard ------------------------------------------------
# The bot MUST run on a real Postgres (Neon) backend. The .env DATABASE_URL is
# authoritative. We forbid the silent SQLite fallback: a missing/empty DATABASE_URL
# is a config error that should crash loudly at startup — NOT reset the user DB on
# every restart. (The old sqlite:///oxygent.db default was the root cause of
# "restart => all users gone": on an ephemeral host SQLite wiped on each boot.)
if not DATABASE_URL or not DATABASE_URL.lower().startswith("postgresql"):
    raise RuntimeError(
        "DATABASE_URL is missing or not a Postgres URL. "
        "OXYGENT requires a persistent Neon Postgres connection — refusing to "
        "start with a volatile/SQLite backend. Set DATABASE_URL in .env."
    )


# --- Connection pool ---------------------------------------------------------
# Opening a fresh TLS connection to remote Neon Postgres costs ~500ms EACH call.
# A pool reuses warm connections (sub-ms) so commands no longer stack that cost.
_POOL = None
_POOL_FALLBACK = False

# Optional isolated schema (set OXYGENT_SCHEMA=test for a staging/clone bot so it
# uses a separate set of tables inside the same DB — no risk to production data).
_OXYGENT_SCHEMA = os.getenv("OXYGENT_SCHEMA", "").strip()


def _apply_schema(raw):
    """Scope this connection to the right schema at runtime.

    - If OXYGENT_SCHEMA is set (clone/staging), use that schema.
    - Otherwise (production/main) explicitly pin to `public` so a connection
      that somehow inherited a different search_path (e.g. a leaked pooled
      connection from a schema-switching test run) can NEVER read/write the
      wrong tables. This is what keeps real users safe.

    We set it per-connection (not as a startup option) because Neon's pooler
    rejects search_path in the startup package. Runtime SET is allowed.

    CRITICAL SAFETY: this is applied on EVERY connection checkout (see get_db)
    so a leaked/wrong pooled connection is always re-pinned before any query.
    """
    target = _OXYGENT_SCHEMA or "public"
    try:
        cur = raw.cursor()
        cur.execute(f"SET search_path TO {target}")
        cur.close()
    except Exception:
        pass
    return raw


def _assert_production_integrity():
    """Startup guard for the production (main) bot.

    If the main bot somehow ends up pointed at a non-public schema and that
    schema is empty/short, we refuse to run rather than serve or mutate the
    wrong tables. This is the final backstop against schema-leak data loss.
    """
    if _OXYGENT_SCHEMA:
        return  # clone/staging is allowed to use its own schema
    try:
        conn = get_db()
        cur = conn.cursor()
        # main must always read `public`
        cur.execute("SELECT count(*) FROM users")
        main_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM public.users")
        public_count = cur.fetchone()[0]
        conn.close()
        if main_count != public_count:
            raise RuntimeError(
                f"[SAFETY] Main bot schema mismatch: search_path users={main_count} "
                f"but public.users={public_count}. Aborting to protect production data."
            )
    except Exception as e:
        # If we cannot verify, crash loudly — never silently serve wrong data.
        raise RuntimeError(f"[SAFETY] Production integrity check failed: {e}")


def _init_pool():
    global _POOL, _POOL_FALLBACK
    try:
        # SimpleConnectionPool: no keys needed, ideal for a single-process async bot.
        # minconn=5, maxconn=50 — generous headroom so concurrent Telegram updates
        # (many users tapping buttons at once) don't exhaust the pool and crash
        # /start. Earlier a small pool (max 10) + leaked connections caused
        # "connection pool exhausted" → new users saw NO response at all.
        _POOL = _psy_pool.SimpleConnectionPool(5, 50, DATABASE_URL, connect_timeout=10)
    except Exception:
        _POOL_FALLBACK = True
        _POOL = None


def get_db():
    """Get a database connection (from pool when available).

    The returned object is a thin wrapper so its .close() returns the
    connection to the pool (instead of dropping it). No call-site changes needed.
    """
    global _POOL, _POOL_FALLBACK
    if _POOL is None and not _POOL_FALLBACK:
        _init_pool()
    if _POOL is not None:
        for attempt in range(3):  # Retry up to 3 times
            try:
                raw = _POOL.getconn()
                break
            except _psy_pool.PoolError:
                if attempt == 2:  # Last attempt
                    # Pool exhausted under load: open a one-off direct connection so the
                    # request still succeeds (degrades gracefully instead of crashing /start).
                    # This prevents the "connection pool exhausted" cascade that dropped
                    # new-user messages.
                    try:
                        raw = psycopg2.connect(DATABASE_URL, connect_timeout=10)
                        return _PooledConn(_apply_schema(raw), None)
                    except Exception:
                        raise
                # Brief wait before retry
                import time
                time.sleep(0.1 * (attempt + 1))
        # Neon drops idle connections; validate before handing out, recycle if dead.
        try:
            cur = raw.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
        except Exception:
            try:
                _POOL.putconn(raw, close=True)
            except Exception:
                pass
            # Retry getting a connection once more
            try:
                raw = _POOL.getconn()
            except _psy_pool.PoolError:
                try:
                    raw = psycopg2.connect(DATABASE_URL, connect_timeout=10)
                    return _PooledConn(_apply_schema(raw), None)
                except Exception:
                    raise
        return _PooledConn(_apply_schema(raw), _POOL)
    # Fallback: direct connect (slow, but keeps the bot running).
    raw = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    return _PooledConn(_apply_schema(raw), None)


class _PooledConn:
    """Wrapper exposing cursor()/commit()/rollback()/close(); close() returns to pool."""

    def __init__(self, raw, pool):
        self._raw = raw
        self._pool = pool

    def cursor(self, *a, **k):
        return self._raw.cursor(*a, **k)

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    @property
    def autocommit(self):
        return self._raw.autocommit

    @autocommit.setter
    def autocommit(self, v):
        self._raw.autocommit = v

    def close(self):
        if self._pool is not None:
            try:
                self._pool.putconn(self._raw)
            except Exception:
                try:
                    self._raw.close()
                except Exception:
                    pass
        else:
            try:
                self._raw.close()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._raw, name)


def _run_migrations(cursor):
    """Idempotent schema migrations. Safe to call every startup.

    CRITICAL: Telegram user IDs are 64-bit (e.g. 7371674958) and overflow a
    32-bit INTEGER. Any column that stores a user_id MUST be BIGINT or the
    referral credit silently fails with NumericValueOutOfRange. The two
    migrations below widen users.referred_by and broadcasts.sent_by if they
    were created as INTEGER. (No-op if already BIGINT.)
    """
    try:
        cursor.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='broadcasts' AND column_name='sent_by'
                      AND data_type='integer'
                ) THEN
                    ALTER TABLE broadcasts ALTER COLUMN sent_by TYPE BIGINT;
                END IF;
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='referred_by'
                      AND data_type='integer'
                ) THEN
                    ALTER TABLE users ALTER COLUMN referred_by TYPE BIGINT;
                END IF;
            END $$;
        """)
    except Exception:
        pass



def init_db():
    """Initialize database tables"""
    _assert_production_integrity()  # backstop: never run on wrong schema
    conn = get_db()
    cursor = conn.cursor()

    # Idempotent migrations (run before TABLE CREATEs that depend on them)
    _run_migrations(cursor)
    conn.commit()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            github_repo TEXT,
            github_token TEXT,
            is_setup INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Channels table (force-join channels)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id BIGINT PRIMARY KEY,
            channel_name TEXT NOT NULL,
            channel_username TEXT,
            added_by BIGINT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Broadcast messages log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            id SERIAL PRIMARY KEY,
            message_text TEXT,
            sent_by INTEGER,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_users INTEGER,
            successful INTEGER
        )
    ''')

    # User states for conversation flow
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            user_id BIGINT PRIMARY KEY,
            state TEXT,
            data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Workers table (Cloudflare Worker hosting)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE,
            worker_name TEXT NOT NULL,
            worker_type TEXT DEFAULT 'website',
            worker_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Settings table (admin-configurable limits)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Payments table (Telegram Stars transactions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            telegram_charge_id TEXT UNIQUE,
            invoice_payload TEXT,
            stars INTEGER,
            credits_added INTEGER,
            currency TEXT DEFAULT 'XTR',
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Sessions table (Code creation sessions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS code_sessions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            session_name TEXT NOT NULL,
            project_type TEXT,
            context_data TEXT,
            code_files TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, session_name)
        )
    ''')

    # Deployments table (Vercel sites / Cloudflare workers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deployments (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            deploy_type TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add new columns to users table if they don't exist (safe for existing DB)
    _new_cols = [
        "referral_code TEXT",
        "referred_by BIGINT DEFAULT 0",
        "bonus_messages INTEGER DEFAULT 0",
        "msg_count INTEGER DEFAULT 0",
        "msg_date TEXT",
        "ref_credited INTEGER DEFAULT 0",
        "voice_enabled INTEGER DEFAULT 0",
        "voice_gender TEXT DEFAULT 'female'",
    ]
    for col in _new_cols:
        col_name = col.split(" ")[0]
        try:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {col}')
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            conn = get_db()
            cursor = conn.cursor()

    # Default settings
    cursor.execute('INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING', ('daily_limit', '20'))
    cursor.execute('INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING', ('referral_bonus', '20'))

    conn.commit()
    conn.close()
    print("[DB] PostgreSQL database initialized successfully!")



# ==================== USER OPERATIONS ====================

def add_user(user_id, username=None, first_name=None, last_name=None):
    """Add or update user in database - only updates user info, NOT github settings.
    Returns True if this was a NEW user (first time seen), False if it was an update.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if user exists first
        cursor.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
        existing = cursor.fetchone()
        if existing:
            # Update only user info, preserve github settings
            cursor.execute('''
                UPDATE users SET username = %s, first_name = %s, last_name = %s
                WHERE user_id = %s
            ''', (username, first_name, last_name, user_id))
            conn.commit()
            return False
        else:
            # Insert new user
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, joined_at)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, username, first_name, last_name, datetime.now()))
            conn.commit()
            return True
    finally:
        conn.close()


def get_user(user_id):
    """Get user by ID"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def update_voice_pref(user_id, enabled=None, gender=None):
    """Set a user's voice preference (enabled flag and/or gender)."""
    conn = get_db()
    cursor = conn.cursor()
    if enabled is not None:
        cursor.execute('UPDATE users SET voice_enabled = %s WHERE user_id = %s', (int(enabled), user_id))
    if gender is not None:
        g = 'male' if str(gender).lower().startswith('m') else 'female'
        cursor.execute('UPDATE users SET voice_gender = %s WHERE user_id = %s', (g, user_id))
    conn.commit()
    conn.close()


def get_voice_pref(user_id):
    """Return (enabled:bool, gender:str) for a user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT voice_enabled, voice_gender FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return (False, 'female')
    return (bool(row[0]), row[1] or 'female')


def update_user_github(user_id, github_repo=None, github_token=None):
    """Update user's GitHub settings"""
    conn = get_db()
    cursor = conn.cursor()
    if github_repo:
        cursor.execute('UPDATE users SET github_repo = %s WHERE user_id = %s', (github_repo, user_id))
    if github_token:
        cursor.execute('UPDATE users SET github_token = %s WHERE user_id = %s', (github_token, user_id))
    cursor.execute('UPDATE users SET is_setup = 1 WHERE user_id = %s AND github_repo IS NOT NULL AND github_token IS NOT NULL', (user_id,))
    conn.commit()
    conn.close()


def get_all_users():
    """Get all users"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return [dict(u) for u in users]


def get_user_count():
    """Get total user count"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        return count
    finally:
        conn.close()


def ban_user(user_id):
    """Ban a user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = %s', (user_id,))
    conn.commit()
    conn.close()


def unban_user(user_id):
    """Unban a user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = %s', (user_id,))
    conn.commit()
    conn.close()


# ==================== SETTINGS / LIMITS ====================

def get_setting(key, default=None):
    """Get a setting value by key"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT value FROM settings WHERE key = %s', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    """Set a setting value"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s', (key, str(value), str(value)))
    conn.commit()
    conn.close()


def get_daily_limit():
    """Get daily message limit per user"""
    try:
        return int(get_setting('daily_limit', '20'))
    except (ValueError, TypeError):
        return 20


# ==================== REFERRAL SYSTEM ====================

import secrets

def generate_referral_code(user_id):
    """Generate a unique referral code for a user"""
    conn = get_db()
    cursor = conn.cursor()
    # Check if user already has a code
    cursor.execute('SELECT referral_code FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        conn.close()
        return row[0]
    # Generate new code
    base = f"{user_id:X}"[:6].upper()
    code = f"OXY{base}"
    # Ensure uniqueness
    cursor.execute('SELECT user_id FROM users WHERE referral_code = %s', (code,))
    while cursor.fetchone():
        code = f"OXY{secrets.token_hex(3).upper()}"
        cursor.execute('SELECT user_id FROM users WHERE referral_code = %s', (code,))
    cursor.execute('UPDATE users SET referral_code = %s WHERE user_id = %s', (code, user_id))
    conn.commit()
    conn.close()
    return code


def get_user_by_referral_code(code):
    """Find user by referral code"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM users WHERE referral_code = %s', (code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def set_referred_by(user_id, referrer_id):
    """Set who referred this user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET referred_by = %s WHERE user_id = %s', (referrer_id, user_id))
    conn.commit()
    conn.close()


def credit_referrer(referrer_id, bonus):
    """Add bonus messages to referrer"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET bonus_messages = bonus_messages + %s WHERE user_id = %s', (bonus, referrer_id))
    conn.commit()
    conn.close()


def get_referred_count(referrer_id):
    """Count users referred by this user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = %s', (referrer_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== MESSAGE LIMIT ====================

def get_msg_count(user_id, date_str):
    """Get message count for user on given date"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT msg_count, msg_date FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return 0, None
    if row['msg_date'] != date_str:
        return 0, date_str  # reset for new day
    return row['msg_count'], row['msg_date']


def increment_msg_count(user_id, date_str):
    """Increment message count for user (resets if new day)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT msg_count, msg_date FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    if row and row[1] == date_str:
        cursor.execute('UPDATE users SET msg_count = msg_count + 1 WHERE user_id = %s', (user_id,))
    else:
        cursor.execute('UPDATE users SET msg_count = 1, msg_date = %s WHERE user_id = %s', (date_str, user_id))
    conn.commit()
    conn.close()


def get_remaining_messages(user_id, date_str):
    """Get remaining messages for user today.

    Free daily allowance and paid bonus credits are tracked as SEPARATE pools:
      - free remaining = daily_limit - today's message count (resets daily)
      - bonus credits spend independently once the free allowance is exhausted
    Returns (remaining, daily, bonus, used) where `remaining` = free_remaining + bonus.

    Uses a single connection (batches limit + msg-count + bonus reads)
    to avoid the ~per-connection Neon latency that made button taps sluggish.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT bonus_messages, msg_count, msg_date FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    if row:
        bonus = int(row[0] or 0)
        today_count = int(row[1] or 0) if row[2] == date_str else 0
    else:
        conn.close()
        return 0, get_daily_limit(), 0, 0
    conn.close()
    daily = get_daily_limit()
    free_remaining = max(0, daily - today_count)
    remaining = free_remaining + bonus
    return remaining, daily, bonus, today_count


def get_user_profile(user_id, date_str=None):
    """Fetch everything needed to render a user's profile/status/refer card in
    ONE database connection (instead of 3-4 separate round-trips).

    Returns a dict:
      {user, remaining, daily, bonus, used, sessions, referred_count}
    Missing user -> None.
    """
    import datetime as _dt
    if date_str is None:
        date_str = _dt.date.today().isoformat()
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Pull the daily LIMIT from settings in the SAME connection (avoids a 2nd
    # get_db()/Neon round-trip that previously dominated button-tap latency).
    cur.execute("SELECT value FROM settings WHERE key = 'daily_limit'")
    _dl = cur.fetchone()
    try:
        daily = int(_dl['value']) if _dl else 20
    except (ValueError, TypeError):
        daily = 20
    # Users + limits + msg_count in one shot
    cur.execute('''
        SELECT user_id, username, first_name, last_name, github_repo, is_setup,
               is_banned, joined_at, referral_code, referred_by, bonus_messages,
               msg_count, msg_date
        FROM users WHERE user_id = %s
    ''', (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return None

    count = int(u['msg_count'] or 0) if u.get('msg_date') == date_str else 0
    bonus = int(u['bonus_messages'] or 0)
    free_remaining = max(0, daily - count)
    remaining = free_remaining + bonus

    # Sessions + referred-count in the SAME connection (RealDictCursor -> dicts)
    cur.execute('SELECT id, session_name, project_type, created_at, updated_at FROM code_sessions WHERE user_id = %s ORDER BY updated_at DESC', (user_id,))
    sessions = [dict(r) for r in cur.fetchall()]
    cur.execute('SELECT COUNT(*) AS c FROM users WHERE referred_by = %s', (user_id,))
    _rc = cur.fetchone()
    referred = _rc['c'] if _rc else 0
    conn.close()

    return {
        'user': dict(u),
        'remaining': remaining,
        'daily': daily,
        'bonus': bonus,
        'used': count,
        'sessions': sessions,
        'referred_count': referred,
    }


# ==================== CHANNEL OPERATIONS ====================

def add_channel(channel_id, channel_name, channel_username=None, added_by=None):
    """Add a force-join channel"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, channel_name, channel_username, added_by)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (channel_id) DO UPDATE SET
            channel_name = EXCLUDED.channel_name,
            channel_username = EXCLUDED.channel_username,
            added_by = EXCLUDED.added_by
    ''', (channel_id, channel_name, channel_username, added_by))
    conn.commit()
    conn.close()
    return True


def remove_channel(channel_id):
    """Remove a force-join channel"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = %s', (int(channel_id),))
    conn.commit()
    conn.close()
    return True


def get_all_channels():
    """Get all force-join channels"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM channels')
    channels = cursor.fetchall()
    conn.close()
    return [dict(c) for c in channels]


def get_channel(channel_id):
    """Get a specific channel"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM channels WHERE channel_id = %s', (channel_id,))
    channel = cursor.fetchone()
    conn.close()
    return dict(channel) if channel else None


# ==================== USER STATES ====================

def set_user_state(user_id, state, data=None):
    """Set user conversation state"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_states (user_id, state, data, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            state = EXCLUDED.state,
            data = EXCLUDED.data,
            updated_at = EXCLUDED.updated_at
    ''', (user_id, state, data, datetime.now()))
    conn.commit()
    conn.close()


def get_user_state(user_id):
    """Get user conversation state"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM user_states WHERE user_id = %s', (user_id,))
    state = cursor.fetchone()
    conn.close()
    return dict(state) if state else None


def clear_user_state(user_id):
    """Clear user conversation state"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_states WHERE user_id = %s', (user_id,))
    conn.commit()
    conn.close()


# ==================== BROADCAST LOG ====================

def log_broadcast(message_text, sent_by, total_users, successful):
    """Log a broadcast message"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO broadcasts (message_text, sent_by, total_users, successful)
        VALUES (%s, %s, %s, %s)
    ''', (message_text, sent_by, total_users, successful))
    conn.commit()
    conn.close()


# ==================== PAYMENTS (TELEGRAM STARS) ====================

def save_payment(user_id, charge_id, payload, stars, credits_added):
    """Save a completed Stars payment (charge_id UNIQUE prevents duplicates)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (user_id, telegram_charge_id, invoice_payload, stars, credits_added, status)
        VALUES (%s, %s, %s, %s, %s, 'completed')
        ON CONFLICT (telegram_charge_id) DO NOTHING
    ''', (user_id, charge_id, payload, stars, credits_added))
    conn.commit()
    conn.close()


def payment_exists(charge_id):
    """Check if a charge_id was already processed (prevents double-credit)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM payments WHERE telegram_charge_id = %s', (charge_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def add_bonus_messages(user_id, amount):
    """Add bonus credits to a user (used by Stars payment)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET bonus_messages = bonus_messages + %s WHERE user_id = %s', (amount, user_id))
    conn.commit()
    conn.close()


def consume_bonus_message(user_id, amount=1):
    """Spend `amount` bonus credits (clamped at 0). Returns credits remaining."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET bonus_messages = GREATEST(bonus_messages - %s, 0) WHERE user_id = %s',
        (amount, user_id)
    )
    cursor.execute('SELECT bonus_messages FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else 0


def get_total_stars_received():
    """Total Stars received across all payments (for admin stats)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COALESCE(SUM(stars), 0) FROM payments')
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_payment_count():
    """Count of completed payments."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM payments')
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== CODE SESSIONS ====================

def create_session(user_id, session_name, project_type=None):
    """Create a new code session for user. Returns session_id or None if name exists."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO code_sessions (user_id, session_name, project_type, context_data, code_files)
            VALUES (%s, %s, %s, '{}', '{}')
            RETURNING id
        ''', (user_id, session_name, project_type))
        session_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return session_id
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return None


def get_user_sessions(user_id):
    """Get all sessions for a user."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('''
        SELECT id, session_name, project_type, created_at, updated_at
        FROM code_sessions
        WHERE user_id = %s
        ORDER BY updated_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_by_id(session_id):
    """Get a specific session by ID."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT * FROM code_sessions WHERE id = %s', (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    if d.get('context_data') and isinstance(d['context_data'], str):
        try:
            d['context_data'] = json.loads(d['context_data'])
        except (json.JSONDecodeError, TypeError):
            d['context_data'] = {}
    if d.get('code_files') and isinstance(d['code_files'], str):
        try:
            d['code_files'] = json.loads(d['code_files'])
        except (json.JSONDecodeError, TypeError):
            d['code_files'] = []
    return d


def update_session_context(session_id, context_data):
    """Merge session context data (preserves existing keys) and sync project_type column."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT context_data FROM code_sessions WHERE id = %s', (session_id,))
    row = cursor.fetchone()
    existing = {}
    if row and row[0]:
        try:
            existing = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing.update(context_data)
    cursor.execute('''
        UPDATE code_sessions SET context_data = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    ''', (json.dumps(existing), session_id))
    # Keep the project_type column in sync so it isn't lost on context updates
    if 'project_type' in context_data:
        cursor.execute('''
            UPDATE code_sessions SET project_type = %s WHERE id = %s
        ''', (context_data['project_type'], session_id))
    conn.commit()
    conn.close()


def update_session_code(session_id, code_files):
    """Update session code files."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE code_sessions SET code_files = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    ''', (json.dumps(code_files), session_id))
    conn.commit()
    conn.close()


def get_session_code(session_id):
    """Return the saved code files for a session as a list of {filename, content}.

    Used to RESUME a build after a timeout/partial failure so the agent continues
    from existing files instead of starting from scratch. Returns [] if none.
    """
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute('SELECT code_files FROM code_sessions WHERE id = %s', (session_id,))
        row = cur.fetchone()
        if not row or not row.get('code_files'):
            return []
        cf = row['code_files']
        if isinstance(cf, str):
            try:
                cf = json.loads(cf)
            except Exception:
                return []
        return cf if isinstance(cf, list) else []
    finally:
        conn.close()


def delete_session(user_id, session_name):
    """Delete a session."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM code_sessions WHERE user_id = %s AND session_name = %s
    ''', (user_id, session_name))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def delete_session_by_id(user_id, session_id):
    """Delete a session by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM code_sessions WHERE user_id = %s AND id = %s
    ''', (user_id, session_id))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def delete_all_sessions(user_id):
    """Delete every session owned by a user. Returns number deleted."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM code_sessions WHERE user_id = %s', (user_id,))
    n = cursor.rowcount
    conn.commit()
    conn.close()
    return n


def get_user_session_count(user_id):
    """Get count of user's sessions."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM code_sessions WHERE user_id = %s', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== ADMIN STATS ====================

def get_channel_count():
    """Get total number of force-join channels."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM channels')
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_bot_stats():
    """Get comprehensive bot statistics for the admin panel.

    Returns a dict with keys: users, banned, referred, channels, sessions,
    active_states, stars, payments, bonus_given, new_24h, top_referrer.
    """
    import datetime as _dt
    conn = get_db()
    cur = conn.cursor()

    stats = {}

    # Total users
    cur.execute('SELECT COUNT(*) FROM users')
    stats['users'] = cur.fetchone()[0]

    # Banned users
    cur.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
    stats['banned'] = cur.fetchone()[0]

    # Users referred by someone
    cur.execute('SELECT COUNT(*) FROM users WHERE referred_by > 0')
    stats['referred'] = cur.fetchone()[0]

    # Channels
    cur.execute('SELECT COUNT(*) FROM channels')
    stats['channels'] = cur.fetchone()[0]

    # Code sessions
    cur.execute('SELECT COUNT(*) FROM code_sessions')
    stats['sessions'] = cur.fetchone()[0]

    # Active user states (users currently in a conversation flow)
    cur.execute('SELECT COUNT(*) FROM user_states')
    stats['active_states'] = cur.fetchone()[0]

    # Total Stars received
    cur.execute('SELECT COALESCE(SUM(stars), 0) FROM payments')
    stats['stars'] = cur.fetchone()[0]

    # Total payments
    cur.execute('SELECT COUNT(*) FROM payments')
    stats['payments'] = cur.fetchone()[0]

    # Total bonus credits given (from referrals)
    cur.execute('SELECT COALESCE(SUM(bonus_messages), 0) FROM users WHERE referred_by > 0')
    stats['bonus_given'] = cur.fetchone()[0]

    # New users in last 24h
    cur.execute("SELECT COUNT(*) FROM users WHERE joined_at >= NOW() - INTERVAL '24 hours'")
    stats['new_24h'] = cur.fetchone()[0]

    # Top referrer
    cur.execute('''
        SELECT referred_by, COUNT(*) AS c
        FROM users WHERE referred_by > 0
        GROUP BY referred_by ORDER BY c DESC LIMIT 1
    ''')
    row = cur.fetchone()
    stats['top_referrer'] = {'referred_by': row[0], 'c': row[1]} if row else None

    conn.close()
    return stats


# ==================== DEPLOYMENT TRACKING ====================

def get_global_max_sites() -> int:
    return int(get_setting('global_max_sites', '5'))


def get_global_max_workers() -> int:
    return int(get_setting('global_max_workers', '5'))


def set_global_max_sites(n: int):
    set_setting('global_max_sites', str(n))


def set_global_max_workers(n: int):
    set_setting('global_max_workers', str(n))


def get_user_deploy_count(uid: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM deployments WHERE user_id=%s AND deploy_type='website'", (uid,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def get_user_worker_count(uid: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM deployments WHERE user_id=%s AND deploy_type='worker'", (uid,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def add_deployment(uid: int, deploy_type: str, name: str, url: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deployments (user_id, deploy_type, name, url) VALUES (%s, %s, %s, %s) RETURNING id",
        (uid, deploy_type, name, url)
    )
    dep_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return dep_id


def remove_deployment(uid: int, deploy_id: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM deployments WHERE id=%s AND user_id=%s", (deploy_id, uid))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_deployment(uid: int, deploy_id: int) -> dict:
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM deployments WHERE id=%s AND user_id=%s", (deploy_id, uid))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_deployments(uid: int, deploy_type: str = None) -> list:
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if deploy_type:
        cur.execute("SELECT * FROM deployments WHERE user_id=%s AND deploy_type=%s ORDER BY created_at DESC", (uid, deploy_type))
    else:
        cur.execute("SELECT * FROM deployments WHERE user_id=%s ORDER BY created_at DESC", (uid,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_user_deploys() -> list:
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('''
        SELECT u.user_id, u.username, u.first_name,
               (SELECT COUNT(*) FROM deployments WHERE user_id=u.user_id AND deploy_type='website') as deploy_count,
               (SELECT COUNT(*) FROM deployments WHERE user_id=u.user_id AND deploy_type='worker') as worker_count
        FROM users u
        WHERE EXISTS (SELECT 1 FROM deployments WHERE user_id=u.user_id)
        ORDER BY (SELECT COUNT(*) FROM deployments WHERE user_id=u.user_id) DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
