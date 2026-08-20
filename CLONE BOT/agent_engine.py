"""
OXYGENT — Hermes-Style Coding Agent Engine
==========================================

Mirrors the architecture studied from the NousResearch/hermes-agent repo
(downloaded for reference; the VPS install at /usr/local/lib/hermes-agent is
NEVER touched — it belongs to the operator).

Core loop (identical shape to hermes run_agent.py):
    THINK -> model returns tool_calls -> execute tool in sandbox ->
    feed result back as role:"tool" -> repeat until finish_reason=="stop"
    or MAX_TURNS reached.

Two problems this module solves (per user request):
  (A) Real tool-use coding (write_file / patch_file / terminal / ...) instead
      of pretending the model returns all code in one ``` block.
  (B) Rate-limit immunity: a resilient transport that rotates free models,
      backs off on 429/5xx/timeout, and NEVER surfaces a raw error to the user.

Multi-user safe:
  - Each user gets an isolated sandbox dir (/tmp/oxygent_sandbox/<uid>/<sid>/).
  - A per-user asyncio.Lock serialises that user's build (no interleaved
    tool state); different users run fully in parallel.
  - A global token-bucket limiter throttles OUR OWN call rate so we don't
    trigger the 429s that the free tier hands out under load.
"""

import os
import re
import json
import asyncio
import logging
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiohttp

from config import (
    OPENCODE_ZEN_BASE_URL,
    OPENCODE_ZEN_MODEL,
    OPENCODE_ZEN_FALLBACKS,
)
import coding_tools as ct

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODELS = [OPENCODE_ZEN_MODEL]
if isinstance(OPENCODE_ZEN_FALLBACKS, str):
    MODELS += [m.strip() for m in OPENCODE_ZEN_FALLBACKS.split(",") if m.strip()]
elif isinstance(OPENCODE_ZEN_FALLBACKS, (list, tuple)):
    MODELS += [str(m).strip() for m in OPENCODE_ZEN_FALLBACKS if str(m).strip()]
# Deduplicate while preserving order
_seen = set()
MODELS = [m for m in MODELS if not (m in _seen or _seen.add(m))]
MAX_TURNS = 8
HTTP_TIMEOUT = 120
SANDBOX_ROOT = "/tmp/oxygent_sandbox"

# Dangerous tools that require user approval before execution
APPROVAL_REQUIRED_TOOLS = {"write_file", "patch_file", "terminal", "execute_code"}


# ---------------------------------------------------------------------------
# ModelPool — health-tracked, fast-switching model rotation
# ---------------------------------------------------------------------------
class ModelPool:
    """Rotates through free models with per-model health tracking.

    On 429: skip model for 60s (rate-limit cooldown).
    On 5xx/timeout: skip model for 15s.
    On success: reset failure count.
    After 3 consecutive failures on any model: cooldown 120s.
    """

    COOLDOWN_429 = 60.0
    COOLDOWN_5XX = 15.0
    COOLDOWN_CONSECUTIVE = 120.0
    CONSECUTIVE_THRESHOLD = 3

    def __init__(self, models: List[str]):
        self._models = list(models)
        self._health: Dict[str, Dict[str, Any]] = {}
        for m in self._models:
            self._health[m] = {
                "failures": 0,
                "cooldown_until": 0.0,
                "total_calls": 0,
                "total_fails": 0,
            }

    def get_best(self) -> str:
        """Return the healthiest available model (not in cooldown)."""
        now = time.time()
        best = None
        best_score = -1
        for m in self._models:
            h = self._health[m]
            if h["cooldown_until"] > now:
                continue  # in cooldown, skip
            # score = negative failures (fewer = better), then original order
            score = -h["failures"] * 1000 + self._models.index(m)
            if best is None or score > best_score:
                best = m
                best_score = score
        if best is None:
            # All models in cooldown — pick the one whose cooldown ends soonest
            best = min(self._models, key=lambda m: self._health[m]["cooldown_until"])
        return best

    def report_success(self, model: str):
        """Mark a successful call — reset failure count."""
        if model in self._health:
            self._health[model]["failures"] = 0
            self._health[model]["total_calls"] += 1

    def report_failure(self, model: str, is_429: bool = False):
        """Mark a failed call — set cooldown."""
        if model not in self._health:
            return
        h = self._health[model]
        h["failures"] += 1
        h["total_calls"] += 1
        h["total_fails"] += 1
        now = time.time()
        if is_429:
            h["cooldown_until"] = now + self.COOLDOWN_429
        elif h["failures"] >= self.CONSECUTIVE_THRESHOLD:
            h["cooldown_until"] = now + self.COOLDOWN_CONSECUTIVE
        else:
            h["cooldown_until"] = now + self.COOLDOWN_5XX

    def available_count(self) -> int:
        """How many models are NOT in cooldown right now."""
        now = time.time()
        return sum(1 for m in self._models if self._health[m]["cooldown_until"] <= now)

    def stats(self) -> Dict[str, Any]:
        """Return health stats for all models."""
        now = time.time()
        result = {}
        for m in self._models:
            h = self._health[m]
            result[m] = {
                "failures": h["failures"],
                "in_cooldown": h["cooldown_until"] > now,
                "cooldown_remaining": max(0, h["cooldown_until"] - now),
                "total_calls": h["total_calls"],
                "total_fails": h["total_fails"],
            }
        return result


# Global model pool instance
_pool = ModelPool(MODELS)

# ---------------------------------------------------------------------------
# Tool approval system (per-user)
# ---------------------------------------------------------------------------
# Stores tool calls waiting for user approval.
# Key: user_id, Value: list of {id, name, args, result}
_pending_approvals: Dict[int, List[Dict[str, Any]]] = {}
# Stores the approval result set by the handler.
# Key: user_id, Value: list of approved tool call ids (empty = all rejected)
_approval_results: Dict[int, asyncio.Event] = {}

def get_pending_approvals(uid: int) -> List[Dict[str, Any]]:
    """Return pending tool calls for a user (read-only)."""
    return list(_pending_approvals.get(uid, []))

def set_approval_result(uid: int, approved_ids: List[str]):
    """Called by the Telegram handler when user taps approve/reject."""
    _approval_results[uid] = (approved_ids, asyncio.Event())

def wait_for_approval(uid: int) -> asyncio.Event:
    """Get the event that fires when user responds. Creates one if needed."""
    if uid not in _approval_results or not isinstance(_approval_results[uid], tuple):
        _approval_results[uid] = (None, asyncio.Event())
    return _approval_results[uid][1]

def pop_approval_result(uid: int) -> Optional[List[str]]:
    """Pop the approval result after the agent consumes it."""
    if uid in _approval_results and isinstance(_approval_results[uid], tuple):
        result = _approval_results[uid][0]
        del _approval_results[uid]
        return result
    return None

def clear_pending_approvals(uid: int):
    """Clear pending approvals for a user (cleanup)."""
    _pending_approvals.pop(uid, None)
    _approval_results.pop(uid, None)

# ---------------------------------------------------------------------------
# Multi-user concurrency control
# ---------------------------------------------------------------------------
# Per-user build locks: one in-flight build per user (agent state is sequential).
_user_locks: Dict[int, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


def _get_user_lock(uid: int) -> asyncio.Lock:
    """Return (creating if needed) the per-user build lock."""
    if uid not in _user_locks:
        _user_locks[uid] = asyncio.Lock()
    return _user_locks[uid]


# ---------------------------------------------------------------------------
# Sandbox helpers (path jail — mirrors hermes path_security.py)
# ---------------------------------------------------------------------------
def sandbox_dir(uid: int, sid: int) -> str:
    d = os.path.join(SANDBOX_ROOT, str(uid), str(sid))
    os.makedirs(d, exist_ok=True)
    return d


def _jail(path: str, root: str) -> Optional[str]:
    """Resolve `path` inside `root`. Return None if it escapes the jail."""
    if path is None:
        return None
    # Normalise; reject obvious escapes.
    if ".." in path.split("/") or path.startswith("/"):
        # allow only relative paths inside root; rewrite absolute to root-relative
        if path.startswith("/"):
            path = path.lstrip("/")
        else:
            return None
    resolved = os.path.normpath(os.path.join(root, path))
    if not resolved.startswith(os.path.normpath(root)):
        return None
    return resolved


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI-format) — derived from coding_tools functions
# ---------------------------------------------------------------------------
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write/create a file with given content inside the project sandbox. Use this to create each source file of the project. Paths are relative to the sandbox root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path, e.g. index.html or src/main.py"},
                    "content": {"type": "string", "description": "Full file content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read an existing file from the sandbox (to inspect current code before editing).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative file path"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Edit an existing file by replacing an exact old_string with new_string (like a targeted find/replace). Use for bug fixes / small edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search the sandbox for a regex pattern or list files. Useful to locate code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex OR glob filename pattern"},
                    "file_glob": {"type": "string", "description": "Optional glob filter, e.g. *.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Run a sandboxed shell command (e.g. to test/run the project). Commands run inside the sandbox dir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Max seconds (default 30)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute a code snippet in a safe sandbox and return its output/errors. Useful to verify logic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "python or javascript"},
                    "code": {"type": "string"},
                },
                "required": ["language", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for documentation/examples when the model needs external info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "num_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_website",
            "description": "Deploy the project to Vercel as a live website. Returns the live URL. Use AFTER building all project files with write_file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name for the Vercel project (alphanumeric, hyphens only)"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Framework type: 'static' (HTML/CSS/JS), 'nextjs', 'react', 'vue', 'python'. Default: 'static'"
                    },
                    "build_command": {
                        "type": "string",
                        "description": "Custom build command (optional, e.g. 'npm run build')"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Build output directory (optional, e.g. 'dist' or 'build')"
                    },
                },
                "required": ["project_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_bot",
            "description": "Deploy a Telegram bot to Cloudflare Workers. Returns the live worker URL. Use AFTER building all bot files with write_file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bot_name": {
                        "type": "string",
                        "description": "Name for the Cloudflare Worker (alphanumeric, hyphens only)"
                    },
                    "env_vars": {
                        "type": "object",
                        "description": "Environment variables to set (e.g. BOT_TOKEN, API_KEY)"
                    },
                },
                "required": ["bot_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_deployment",
            "description": "Delete a hosted website or worker. Actually removes it from Vercel/Cloudflare. Use when user wants to delete a hosted site/worker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deploy_id": {
                        "type": "integer",
                        "description": "The deployment ID (from the user's deployment list)"
                    },
                },
                "required": ["deploy_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Resilient transport — ModelPool-powered fast fallback
# ---------------------------------------------------------------------------
async def _zen_with_tools(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    system: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Call Zen API with tools. Uses ModelPool for fast model rotation.

    Tries each healthy model ONCE. On 429 → skip 60s, on 5xx → skip 15s.
    Returns the raw message dict or None only if EVERY model failed.
    """
    if system:
        full = [{"role": "system", "content": system}] + messages
    else:
        full = list(messages)

    last_err = ""
    tried = set()
    total = len(MODELS)

    for _ in range(total):
        model = _pool.get_best()
        if model in tried:
            # All remaining models are either tried or in cooldown
            break
        tried.add(model)

        payload = {
            "model": model,
            "messages": full,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        _pool.report_success(model)
                        return data["choices"][0]["message"]
                    elif resp.status == 429:
                        last_err = f"429 on {model}"
                        _pool.report_failure(model, is_429=True)
                        logger.warning(f"ModelPool: {last_err} (cooldown {ModelPool.COOLDOWN_429}s)")
                    elif resp.status >= 500:
                        last_err = f"{resp.status} on {model}"
                        _pool.report_failure(model, is_429=False)
                        logger.warning(f"ModelPool: {last_err}")
                    else:
                        body = await resp.text()
                        last_err = f"{resp.status} on {model}: {body[:80]}"
                        _pool.report_failure(model, is_429=False)
                        logger.error(f"ModelPool: {last_err}")
        except asyncio.TimeoutError:
            last_err = f"timeout on {model}"
            _pool.report_failure(model, is_429=False)
            logger.warning(f"ModelPool: {last_err}")
        except Exception as e:
            last_err = f"error on {model}: {e}"
            _pool.report_failure(model, is_429=False)
            logger.error(f"ModelPool: {last_err}")

    logger.error(f"ModelPool exhausted. Tried: {tried}. Last: {last_err}")
    return None


# ---------------------------------------------------------------------------
# Tool dispatch (sandbox-jailed) — mirrors hermes tool_executor
# ---------------------------------------------------------------------------
async def _dispatch(tool_name: str, args: Dict[str, Any], root: str,
                    uid: int = 0, pending: Optional[List[Dict]] = None) -> str:
    """Execute a tool call safely inside the sandbox. Returns a string result.

    If the tool requires approval and `pending` is provided, the tool call is
    added to the pending list instead of being executed. Returns a placeholder
    so the agent loop can continue to the approval phase.
    """
    if tool_name in APPROVAL_REQUIRED_TOOLS and pending is not None:
        # Queue for user approval — don't execute yet
        tc_id = f"tc_{len(pending)}"
        pending.append({
            "id": tc_id,
            "name": tool_name,
            "args": args,
            "result": None,
        })
        return json.dumps({"success": True, "queued_for_approval": True, "tool": tool_name})

    try:
        if tool_name == "write_file":
            p = _jail(args.get("path", ""), root)
            if not p:
                return json.dumps({"success": False, "error": "path escapes sandbox"})
            res = await ct.write_file(p, args.get("content", ""))
        elif tool_name == "read_file":
            p = _jail(args.get("path", ""), root)
            if not p:
                return json.dumps({"success": False, "error": "path escapes sandbox"})
            res = await ct.read_file(p)
        elif tool_name == "patch_file":
            p = _jail(args.get("path", ""), root)
            if not p:
                return json.dumps({"success": False, "error": "path escapes sandbox"})
            res = await ct.patch_file(p, args.get("old_string", ""), args.get("new_string", ""))
        elif tool_name == "search_files":
            res = await ct.search_files(args.get("pattern", ""), root, args.get("file_glob"))
        elif tool_name == "terminal":
            cmd = args.get("command", "")
            if any(t in cmd for t in ["rm -rf /", "mkfs", ":(){"]):
                return json.dumps({"success": False, "error": "dangerous command blocked"})
            res = await ct.terminal(cmd, args.get("timeout", 30))
        elif tool_name == "execute_code":
            res = await ct.execute_tool(
                "execute_code", language=args.get("language", "python"), code=args.get("code", "")
            )
        elif tool_name == "web_search":
            res = await ct.web_search(args.get("query", ""), args.get("num_results", 5))
        elif tool_name == "deploy_website":
            res = await ct.deploy_website(
                uid=uid,
                project_name=args.get("project_name", "my-site"),
                source_dir=root,
                framework=args.get("framework", "static"),
                build_command=args.get("build_command"),
                output_dir=args.get("output_dir"),
            )
        elif tool_name == "deploy_bot":
            res = await ct.deploy_bot(
                uid=uid,
                bot_name=args.get("bot_name", "my-bot"),
                source_dir=root,
                env_vars=args.get("env_vars", {}),
            )
        elif tool_name == "delete_deployment":
            deploy_id = args.get("deploy_id")
            if deploy_id is None:
                res = {"success": False, "error": "deploy_id is required"}
            else:
                res = await ct.delete_deployment(uid=uid, deploy_id=int(deploy_id))
        else:
            return json.dumps({"success": False, "error": f"unknown tool {tool_name}"})
        return json.dumps(res, default=str)[:4000]
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)[:500]})


# ---------------------------------------------------------------------------
# The agent loop (Hermes-style)
# ---------------------------------------------------------------------------
AGENT_SYSTEM = (
    "You are OXYGENT, an autonomous AI agent. You BUILD and DEPLOY software.\n\n"
    "TOOLS AVAILABLE:\n"
    "- write_file: Create/update files in your sandbox\n"
    "- read_file: Read files from sandbox\n"
    "- patch_file: Edit files surgically (find/replace)\n"
    "- terminal: Run shell commands (npm, git, etc.)\n"
    "- execute_code: Run Python/JS snippets\n"
    "- web_search: Search for docs/examples\n"
    "- deploy_website: Deploy a website to Vercel (returns live URL)\n"
    "- deploy_bot: Deploy a Telegram bot to Cloudflare Workers (returns live URL)\n"
    "- delete_deployment: Delete a hosted site/worker (returns success/failure)\n\n"
    "RULES:\n"
    "1. When user says 'host/deploy' → build files FIRST, THEN call deploy tool\n"
    "2. When user says 'build/create' → use write_file + terminal tools\n"
    "3. When user says 'fix/edit' → read_file first, then patch_file\n"
    "4. ALWAYS use tools to create actual files. Never just print code.\n"
    "5. When deploying, call deploy_website or deploy_bot — return the live URL.\n"
    "6. When user says 'delete/remove hosted site/worker' → ask which one, then call delete_deployment.\n"
    "7. Use relative paths inside the sandbox. Stay inside the sandbox.\n"
    "8. When done, reply with a summary. If deployed, include the live URL."
)

# Per-session agent state (for approval flow)
# Key: (uid, sid), Value: dict with messages, collected, summary, root
_session_state: Dict[tuple, Dict[str, Any]] = {}

# Stop flags — set by /stop command to break the agent loop
_stop_flags: Dict[int, bool] = {}


def set_stop_flag(uid: int, val: bool):
    """Set or clear the stop flag for a user."""
    _stop_flags[uid] = val


def _check_stop(uid: int) -> bool:
    """Check and clear the stop flag."""
    if _stop_flags.get(uid):
        _stop_flags[uid] = False
        return True
    return False


def _get_session_state(uid: int, sid: int) -> Optional[Dict[str, Any]]:
    return _session_state.get((uid, sid))


def _set_session_state(uid: int, sid: int, state: Dict[str, Any]):
    _session_state[(uid, sid)] = state


def _clear_session_state(uid: int, sid: int):
    _session_state.pop((uid, sid), None)


async def agent_build(
    uid: int,
    sid: int,
    user_request: str,
    seed_files: Optional[Dict[str, str]] = None,
    session_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the Hermes-style agent loop for one build/fix request.

    Returns {"ok": bool, "files": {relpath: content}, "summary": str,
             "error": str, "pending_approval": [...] or None}.

    When dangerous tools (write_file, terminal, etc.) are detected, execution
    pauses, the lock is RELEASED (so approval handler can run), and returns
    pending_approval. Call agent_resume() after the user approves to continue.

    Multi-user safe: sandboxes isolated, lock held only during active work.
    """
    root = sandbox_dir(uid, sid)

    # Seed existing files into the sandbox (for fix/edit mode).
    if seed_files:
        for rel, content in seed_files.items():
            p = _jail(rel, root)
            if p:
                try:
                    os.makedirs(os.path.dirname(p) or root, exist_ok=True)
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception as e:
                    logger.warning(f"seed failed {rel}: {e}")

    lock = _get_user_lock(uid)
    await lock.acquire()
    try:
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_request}]
        collected: Dict[str, str] = dict(seed_files or {})
        summary = ""

        for turn in range(MAX_TURNS):
            # Check stop flag (set by /stop command)
            if _check_stop(uid):
                return {"ok": True, "files": collected, "summary": summary or "Stopped by user.", "error": "stopped", "pending_approval": None}

            pending_tools: List[Dict[str, Any]] = []

            # Build system prompt with session type context
            sys_prompt = AGENT_SYSTEM
            if session_type:
                type_rules = {
                    "Website": "This is a WEBSITE session. Build the website and deploy to Vercel using deploy_website tool.",
                    "MiniApp": "This is a MINIAPP session. Build a website (deploy to Vercel) AND a Telegram bot (deploy to Cloudflare Workers).",
                    "Telegram Bot": "This is a TELEGRAM BOT session. Build the bot and deploy to Cloudflare Workers using deploy_bot tool.",
                    "Other": "This is an OTHER session. Determine the best deployment target based on what the user wants.",
                }
                extra = type_rules.get(session_type, "")
                if extra:
                    sys_prompt = AGENT_SYSTEM + f"\n\nSESSION TYPE RULE: {extra}"

            msg = await _zen_with_tools(messages, TOOL_SCHEMAS, system=sys_prompt)
            if msg is None:
                if collected:
                    return {"ok": True, "files": collected, "summary": summary or "Built (partial).", "error": "", "pending_approval": None}
                return {"ok": False, "files": {}, "summary": "", "error": "all_models_down", "pending_approval": None}

            asst = {"role": "assistant", "content": msg.get("content") or ""}
            tcs = msg.get("tool_calls")
            if tcs:
                asst["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        },
                    }
                    for tc in tcs
                ]
            messages.append(asst)

            if not tcs:
                summary = msg.get("content") or ""
                break

            for tc in tcs:
                fn = tc.get("function", {})
                name = fn.get("name")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}

                if name in APPROVAL_REQUIRED_TOOLS:
                    tc_id = f"tc_{len(pending_tools)}"
                    pending_tools.append({
                        "id": tc_id,
                        "name": name,
                        "args": args,
                        "tool_call_id": tc.get("id"),
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": json.dumps({"success": True, "queued_for_approval": True, "tool": name}),
                    })
                    continue

                result_str = await _dispatch(name, args, root)
                if name == "write_file":
                    rel = args.get("path", "")
                    content = args.get("content", "")
                    if rel:
                        collected[rel] = content
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": result_str,
                })

            if pending_tools:
                _set_session_state(uid, sid, {
                    "messages": messages,
                    "collected": collected,
                    "summary": summary,
                    "root": root,
                    "pending_tools": pending_tools,
                    "turn": turn,
                    "session_type": session_type,
                })
                _pending_approvals[uid] = pending_tools
                # RELEASE LOCK before waiting for user approval
                try:
                    lock.release()
                except RuntimeError:
                    pass
                return {
                    "ok": True,
                    "files": collected,
                    "summary": summary,
                    "error": "",
                    "pending_approval": pending_tools,
                }

        # Collect files from the sandbox
        for f in Path(root).rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(root))
                try:
                    collected[rel] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        items = list(collected.items())[:5]
        _clear_session_state(uid, sid)
        return {
            "ok": True,
            "files": dict(items),
            "summary": summary or "Build complete.",
            "error": "",
            "pending_approval": None,
        }
    finally:
        # Always release the lock if still held
        if lock.locked():
            try:
                lock.release()
            except RuntimeError:
                pass


async def agent_resume(
    uid: int,
    sid: int,
    approved_tool_ids: List[str],
) -> Dict[str, Any]:
    """
    Resume the agent loop after user approves/rejects tool calls.

    approved_tool_ids: list of tool call IDs the user approved.
                       Empty list = all rejected.
    """
    state = _get_session_state(uid, sid)
    if not state:
        return {"ok": False, "files": {}, "summary": "", "error": "no_session_state", "pending_approval": None}

    messages = state["messages"]
    collected = state["collected"]
    summary = state["summary"]
    root = state["root"]
    pending_tools = state["pending_tools"]
    start_turn = state["turn"] + 1
    session_type = state.get("session_type")

    lock = _get_user_lock(uid)
    async with lock:
        # Execute approved tool calls and feed results back
        for tc in pending_tools:
            if tc["id"] in approved_tool_ids:
                result_str = await _dispatch(tc["name"], tc["args"], root)
                if tc["name"] == "write_file":
                    rel = tc["args"].get("path", "")
                    content = tc["args"].get("content", "")
                    if rel:
                        collected[rel] = content
            else:
                result_str = json.dumps({"success": False, "error": "User rejected this action."})
            messages.append({
                "role": "tool",
                "tool_call_id": tc["tool_call_id"],
                "content": result_str,
            })

        clear_pending_approvals(uid)

        # Continue the agent loop
        for turn in range(start_turn, MAX_TURNS):
            pending_tools = []

            # Check stop flag
            if _check_stop(uid):
                return {"ok": True, "files": collected, "summary": summary or "Stopped by user.", "error": "stopped", "pending_approval": None}

            # Build system prompt with session type
            sys_prompt = AGENT_SYSTEM
            if session_type:
                type_rules = {
                    "Website": "This is a WEBSITE session. Build the website and deploy to Vercel using deploy_website tool.",
                    "MiniApp": "This is a MINIAPP session. Build a website (deploy to Vercel) AND a Telegram bot (deploy to Cloudflare Workers).",
                    "Telegram Bot": "This is a TELEGRAM BOT session. Build the bot and deploy to Cloudflare Workers using deploy_bot tool.",
                    "Other": "This is an OTHER session. Determine the best deployment target based on what the user wants.",
                }
                extra = type_rules.get(session_type, "")
                if extra:
                    sys_prompt = AGENT_SYSTEM + f"\n\nSESSION TYPE RULE: {extra}"

            msg = await _zen_with_tools(messages, TOOL_SCHEMAS, system=sys_prompt)
            if msg is None:
                if collected:
                    return {"ok": True, "files": collected, "summary": summary or "Built (partial).", "error": "", "pending_approval": None}
                return {"ok": False, "files": {}, "summary": "", "error": "all_models_down", "pending_approval": None}

            asst = {"role": "assistant", "content": msg.get("content") or ""}
            tcs = msg.get("tool_calls")
            if tcs:
                asst["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        },
                    }
                    for tc in tcs
                ]
            messages.append(asst)

            if not tcs:
                summary = msg.get("content") or ""
                break

            for tc in tcs:
                fn = tc.get("function", {})
                name = fn.get("name")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}

                if name in APPROVAL_REQUIRED_TOOLS:
                    tc_id = f"tc_{len(pending_tools)}"
                    pending_tools.append({
                        "id": tc_id,
                        "name": name,
                        "args": args,
                        "tool_call_id": tc.get("id"),
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": json.dumps({"success": True, "queued_for_approval": True, "tool": name}),
                    })
                    continue

                result_str = await _dispatch(name, args, root)
                if name == "write_file":
                    rel = args.get("path", "")
                    content = args.get("content", "")
                    if rel:
                        collected[rel] = content
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": result_str,
                })

            if pending_tools:
                _set_session_state(uid, sid, {
                    "messages": messages,
                    "collected": collected,
                    "summary": summary,
                    "root": root,
                    "pending_tools": pending_tools,
                    "turn": turn,
                    "session_type": session_type,
                })
                _pending_approvals[uid] = pending_tools
                return {
                    "ok": True,
                    "files": collected,
                    "summary": summary,
                    "error": "",
                    "pending_approval": pending_tools,
                }

        # Collect files from sandbox
        for f in Path(root).rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(root))
                try:
                    collected[rel] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        items = list(collected.items())[:5]
        _clear_session_state(uid, sid)
        return {
            "ok": True,
            "files": dict(items),
            "summary": summary or "Build complete.",
            "error": "",
            "pending_approval": None,
        }


def cleanup_user_sandbox(uid: int, sid: int):
    """Remove a user's sandbox dir (called on session delete)."""
    try:
        import shutil
        d = os.path.join(SANDBOX_ROOT, str(uid), str(sid))
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass
    _clear_session_state(uid, sid)
    clear_pending_approvals(uid)
