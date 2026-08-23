"""
OXYGENT — Hermes-Style Coding Agent Engine
=========================================

This module implements an autonomous coding agent inspired by the
NousResearch/hermes-agent architecture. It enables the bot to build
software by calling tools in a sandboxed environment.

Core Architecture:
    The agent follows a THINK → ACT → OBSERVE loop:
    1. Model receives user request and context
    2. Model returns tool_calls (or text if done)
    3. Tools execute in isolated sandbox
    4. Results fed back as role:"tool" messages
    5. Loop repeats until finish_reason=="stop" or MAX_TURNS

Key Features:
    (A) Real tool-use coding — write_file, patch_file, terminal, etc.
        instead of returning all code in a single markdown block
    (B) Rate-limit immunity — rotates through free models with exponential
        backoff on 429/5xx/timeout errors
    (C) Multi-user isolation — per-user sandboxes and locks prevent
        cross-contamination

Safety:
    - Path jail prevents sandbox escapes (no ".." or absolute paths)
    - Dangerous tools require user approval before execution
    - Commands like "rm -rf /" are blocked
    - Per-user asyncio.Lock serializes builds (no interleaved state)

Sandbox Structure:
    /tmp/oxygent_sandbox/
    └── <uid>/
        └── <sid>/
            ├── src/
            │   └── main.py
            └── index.html

Usage:
    result = await agent_build(uid, sid, "Build a calculator app")
    if result["ok"]:
        files = result["files"]  # {relpath: content}
        summary = result["summary"]

Author: OXYCODE TEAM
"""

import os
import re
import json
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiohttp

import database as db
import coding_tools as ct
import providers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_TURNS = 25
HTTP_TIMEOUT = 90
BACKOFF_BASE = 2
MAX_ATTEMPTS_PER_TURN = 2

SANDBOX_ROOT = "/tmp/oxygent_sandbox"

# Dangerous tools that require user approval before execution
APPROVAL_REQUIRED_TOOLS = {"write_file", "patch_file", "terminal", "execute_code"}

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
            "name": "list_files",
            "description": "List all files in the sandbox or a subdirectory. Shows file tree structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Subdirectory to list (default: root)"},
                    "pattern": {"type": "string", "description": "Optional glob pattern filter"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents for a regex pattern across the sandbox. Returns matching lines with file paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Subdirectory to search in (default: root)"},
                    "file_glob": {"type": "string", "description": "Optional file filter e.g. *.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_init",
            "description": "Initialize a git repository in the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage all files and create a git commit in the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent git commit history in the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of commits to show (default 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_review",
            "description": "Review code quality of a file or the entire project. Returns issues, suggestions, and improvements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory to review (default: root)"},
                    "focus": {"type": "string", "description": "Focus area: bugs, performance, security, or general"},
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Resilient transport — native tool-calling, model rotation, backoff
# ---------------------------------------------------------------------------
async def _zen_with_tools(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    system: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call AI API with tools using provider fallback chain.
    
    Priority:
    1. OpenCode (free, IP-based, no API key) — primary
    2. Active configured provider from admin panel
    3. All other working providers
    
    Returns the raw message dict or None if ALL providers/models failed.
    """
    if system:
        full = [{"role": "system", "content": system}] + messages
    else:
        full = list(messages)

    last_err = ""

    # ── 1. Try OpenCode first (free, no API key) ──
    oc_config = providers.get_opencode_config()
    oc_base = oc_config["base_url"].rstrip("/")
    oc_models = oc_config["models"]

    for attempt in range(MAX_ATTEMPTS_PER_TURN * len(oc_models)):
        current_model = oc_models[attempt % len(oc_models)]
        payload = {
            "model": current_model,
            "messages": full,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "opencode/1.18.16",
        }
        chat_url = oc_base + "/chat/completions"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    chat_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "choices" in data and data["choices"]:
                            return data["choices"][0]["message"]
                        last_err = f"empty response from {current_model}"
                    elif resp.status == 429:
                        last_err = f"429 rate-limit on {current_model} (OpenCode)"
                        logger.warning(last_err)
                    elif resp.status >= 500:
                        last_err = f"{resp.status} server error on {current_model} (OpenCode)"
                        logger.warning(last_err)
                    else:
                        body = await resp.text()
                        last_err = f"{resp.status} {body[:120]}"
                        logger.error(f"OpenCode API error: {last_err}")
        except asyncio.TimeoutError:
            last_err = f"timeout on {current_model} (OpenCode) after {HTTP_TIMEOUT}s"
            logger.warning(last_err)
        except Exception as e:
            last_err = f"exception on {current_model} (OpenCode): {e}"
            logger.error(last_err)

        if "429" in last_err:
            await asyncio.sleep(min(8.0, BACKOFF_BASE ** min(attempt, 3)))
        else:
            await asyncio.sleep(min(2.0, BACKOFF_BASE ** min(attempt, 1)))

    logger.info("OpenCode failed, falling back to configured providers")

    # ── 2. Try active configured provider ──
    active = providers.get_provider_for_request()
    if active:
        config = providers.get_provider_config(active)
        base_url = config["base_url"]
        api_key = config["api_key"]
        model = config["model"]
        models_list = config["models"] or [model]

        for attempt in range(MAX_ATTEMPTS_PER_TURN * len(models_list)):
            current_model = models_list[attempt % len(models_list)]
            payload = {
                "model": current_model,
                "messages": full,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
            }
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            chat_url = base_url.rstrip("/")
            if not chat_url.endswith("/chat/completions"):
                chat_url = chat_url + ("/chat/completions" if chat_url.endswith("/v1") else "/v1/chat/completions")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        chat_url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if "choices" in data and data["choices"]:
                                return data["choices"][0]["message"]
                            last_err = f"empty response from {current_model}"
                        elif resp.status == 429:
                            last_err = f"429 rate-limit on {current_model} ({active['name']})"
                            logger.warning(last_err)
                        else:
                            body = await resp.text()
                            last_err = f"{resp.status} {body[:120]}"
                            logger.error(f"Provider API error: {last_err}")
            except asyncio.TimeoutError:
                last_err = f"timeout on {current_model} after {HTTP_TIMEOUT}s"
                logger.warning(last_err)
            except Exception as e:
                last_err = f"exception on {current_model}: {e}"
                logger.error(last_err)

            if "429" in last_err:
                await asyncio.sleep(min(8.0, BACKOFF_BASE ** min(attempt, 3)))
            else:
                await asyncio.sleep(min(2.0, BACKOFF_BASE ** min(attempt, 1)))

    # ── 3. Fallback to ALL other working providers ──
    working = db.get_working_providers()
    if working:
        logger.info(f"Falling back to {len(working)} other working providers")
        for fallback_provider in working:
            # skip OpenCode DB entry (already tried) and active (already tried)
            pid = fallback_provider.get("id")
            active_id = (active or {}).get("id")
            if pid == active_id:
                continue
            config = providers.get_provider_config(fallback_provider)
            base_url = config["base_url"]
            api_key = config["api_key"]
            model = config["model"]
            models_list = config["models"] or [model]

            for attempt in range(2):
                current_model = models_list[attempt % len(models_list)]
                payload = {
                    "model": current_model,
                    "messages": full,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": False,
                }
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                chat_url = base_url.rstrip("/")
                if not chat_url.endswith("/chat/completions"):
                    chat_url = chat_url + ("/chat/completions" if chat_url.endswith("/v1") else "/v1/chat/completions")

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            chat_url, headers=headers, json=payload,
                            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if "choices" in data and data["choices"]:
                                    return data["choices"][0]["message"]
                                last_err = f"empty response from {current_model}"
                            elif resp.status == 429:
                                last_err = f"429 rate-limit on {current_model} ({fallback_provider['name']})"
                                logger.warning(last_err)
                            else:
                                body = await resp.text()
                                last_err = f"{resp.status} {body[:120]}"
                                logger.error(f"Fallback provider error: {last_err}")
                except asyncio.TimeoutError:
                    last_err = f"timeout on {current_model}"
                    logger.warning(last_err)
                except Exception as e:
                    last_err = f"exception on {current_model}: {e}"
                    logger.error(last_err)
                await asyncio.sleep(2.0)

    logger.error(f"No providers available or all failed. Last error: {last_err}")
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
        elif tool_name == "list_files":
            target = _jail(args.get("path", "") or "", root)
            if not target:
                return json.dumps({"success": False, "error": "path escapes sandbox"})
            pattern = args.get("pattern", "*")
            files = []
            try:
                for f in Path(target).rglob(pattern):
                    if f.is_file():
                        rel = str(f.relative_to(root))
                        files.append(rel)
                res = {"success": True, "files": files[:200]}
            except Exception as e:
                res = {"success": False, "error": str(e)}
        elif tool_name == "grep":
            target_dir = _jail(args.get("path", "") or "", root)
            if not target_dir:
                return json.dumps({"success": False, "error": "path escapes sandbox"})
            pattern = args.get("pattern", "")
            file_glob = args.get("file_glob")
            matches = []
            try:
                import re as _re
                regex = _re.compile(pattern)
                glob_pattern = file_glob or "**/*"
                for f in Path(target_dir).rglob(glob_pattern):
                    if f.is_file():
                        try:
                            text = f.read_text(encoding="utf-8", errors="replace")
                            for i, line in enumerate(text.splitlines(), 1):
                                if regex.search(line):
                                    rel = str(f.relative_to(root))
                                    matches.append(f"{rel}:{i}: {line.strip()[:120]}")
                                    if len(matches) >= 50:
                                        break
                        except Exception:
                            pass
                        if len(matches) >= 50:
                            break
                res = {"success": True, "matches": matches, "total": len(matches)}
            except Exception as e:
                res = {"success": False, "error": str(e)}
        elif tool_name == "git_init":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "init", cwd=root,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                res = {"success": True, "output": "git initialized"}
            except Exception as e:
                res = {"success": False, "error": str(e)}
        elif tool_name == "git_commit":
            try:
                await asyncio.create_subprocess_exec(
                    "git", "add", "-A", cwd=root,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                proc = await asyncio.create_subprocess_exec(
                    "git", "commit", "-m", args.get("message", "Update"),
                    cwd=root,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                res = {"success": proc.returncode == 0, "output": (stdout or stderr).decode()[:2000]}
            except Exception as e:
                res = {"success": False, "error": str(e)}
        elif tool_name == "git_log":
            limit = args.get("limit", 10)
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "log", f"--oneline", f"-{limit}",
                    cwd=root,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                res = {"success": True, "log": (stdout or b"").decode()[:2000]}
            except Exception as e:
                res = {"success": False, "error": str(e)}
        elif tool_name == "code_review":
            target = _jail(args.get("path", "") or "", root)
            if not target:
                return json.dumps({"success": False, "error": "path escapes sandbox"})
            focus = args.get("focus", "general")
            issues = []
            try:
                files_to_review = []
                p = Path(target)
                if p.is_file():
                    files_to_review = [p]
                else:
                    for f in p.rglob("*"):
                        if f.is_file() and f.suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json"}:
                            files_to_review.append(f)
                for f in files_to_review[:10]:
                    try:
                        text = f.read_text(encoding="utf-8", errors="replace")
                        lines = text.splitlines()
                        rel = str(f.relative_to(root))
                        if focus in ("bugs", "general"):
                            for i, line in enumerate(lines, 1):
                                if "eval(" in line or "exec(" in line:
                                    issues.append(f"{rel}:{i}: Potential security issue - eval/exec usage")
                                if "except:" in line or "except Exception:" in line:
                                    issues.append(f"{rel}:{i}: Broad exception catch - consider specific exceptions")
                        if focus in ("performance", "general"):
                            for i, line in enumerate(lines, 1):
                                if "import *" in line:
                                    issues.append(f"{rel}:{i}: Wildcard import - use specific imports")
                        if focus == "security":
                            for i, line in enumerate(lines, 1):
                                if any(x in line for x in ["password", "secret", "token", "api_key"]):
                                    if "=" in line and "\"" in line:
                                        issues.append(f"{rel}:{i}: Possible hardcoded secret")
                    except Exception:
                        pass
                res = {"success": True, "issues": issues[:30], "files_reviewed": len(files_to_review)}
            except Exception as e:
                res = {"success": False, "error": str(e)}
        else:
            return json.dumps({"success": False, "error": f"unknown tool {tool_name}"})
        return json.dumps(res, default=str)[:4000]
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)[:500]})


# ---------------------------------------------------------------------------
# The agent loop (Hermes-style)
# ---------------------------------------------------------------------------
AGENT_SYSTEM = (
    "You are OXYGENT, an autonomous AI coding AGENT running inside a per-user "
    "sandbox. You BUILD software by calling tools, not by printing code. "
    "RULES:\n"
    "1. Create each file with the write_file tool (relative paths only).\n"
    "2. To fix/edit, read_file then patch_file (do NOT recreate everything).\n"
    "3. You may run terminal/execute_code to test.\n"
    "4. Use list_files to see project structure, grep to search code, code_review to check quality.\n"
    "5. Use git_init/git_commit to version your work as you build.\n"
    "6. When the project is complete, reply with a short summary (no tool calls).\n"
    "7. NEVER use absolute paths or '..'. Stay inside the sandbox.\n"
    "8. You have up to 25 turns — plan your approach before diving in."
)

# Per-session agent state (for approval flow)
# Key: (uid, sid), Value: dict with messages, collected, summary, root
_session_state: Dict[tuple, Dict[str, Any]] = {}


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
            pending_tools: List[Dict[str, Any]] = []

            msg = await _zen_with_tools(messages, TOOL_SCHEMAS, system=AGENT_SYSTEM)
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

            msg = await _zen_with_tools(messages, TOOL_SCHEMAS, system=AGENT_SYSTEM)
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
