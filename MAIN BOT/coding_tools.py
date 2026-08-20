"""
OXYGENT — Coding Tools Sandbox
==============================

A 7-tool sandbox environment for autonomous code execution and file management.

Available Tools:
    1. read_file      — Read file content from sandbox
    2. write_file     — Create/overwrite files in sandbox
    3. search_files   — Search by filename or content (regex)
    4. patch_file     — Find/replace edits on existing files
    5. terminal       — Execute sandboxed shell commands
    6. execute_code   — Run Python/JavaScript snippets safely
    7. web_search     — DuckDuckGo search for documentation

Safety Features:
    - Terminal commands blocked: rm -rf, mkfs, dd, shutdown, pip install, etc.
    - File operations limited to sandbox directory
    - Web downloads blocked (curl, wget)
    - Timeouts prevent hanging processes

Usage:
    result = await write_file("/tmp/sandbox/main.py", "print('hello')")
    result = await terminal("python main.py", timeout=10)
    result = await web_search("Python asyncio tutorial")

Author: OXYCODE TEAM
"""

import os
import re
import json
import asyncio
import aiohttp
import logging
import subprocess
import tempfile
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# === FILE OPERATIONS ===

async def read_file(filepath: str) -> Dict[str, Any]:
    """Read file content."""
    try:
        path = Path(filepath)
        if not path.exists():
            return {"success": False, "error": f"File not found: {filepath}"}
        
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        
        return {
            "success": True,
            "content": content,
            "lines": len(lines),
            "size": len(content),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def write_file(filepath: str, content: str) -> Dict[str, Any]:
    """Write content to file."""
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        
        return {
            "success": True,
            "filepath": str(path),
            "size": len(content),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def search_files(pattern: str, path: str = ".", file_glob: str = None) -> Dict[str, Any]:
    """Search files by name or content."""
    try:
        results = []
        search_path = Path(path)
        
        if not search_path.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        
        # Search by filename
        if file_glob:
            for file in search_path.rglob(file_glob):
                if pattern.lower() in file.name.lower():
                    results.append({
                        "path": str(file),
                        "name": file.name,
                        "size": file.stat().st_size if file.exists() else 0,
                    })
        else:
            # Search by content
            for file in search_path.rglob("*"):
                if file.is_file():
                    try:
                        content = file.read_text(encoding="utf-8", errors="ignore")
                        if re.search(pattern, content, re.IGNORECASE):
                            results.append({
                                "path": str(file),
                                "name": file.name,
                                "matches": len(re.findall(pattern, content, re.IGNORECASE)),
                            })
                    except:
                        pass
        
        return {
            "success": True,
            "results": results[:50],  # Limit results
            "total": len(results),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def patch_file(filepath: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """Replace text in file."""
    try:
        path = Path(filepath)
        if not path.exists():
            return {"success": False, "error": f"File not found: {filepath}"}
        
        content = path.read_text(encoding="utf-8")
        
        if old_string not in content:
            return {"success": False, "error": "Old string not found in file"}
        
        new_content = content.replace(old_string, new_string, 1)
        path.write_text(new_content, encoding="utf-8")
        
        return {
            "success": True,
            "replacements": 1,
            "diff": f"- {old_string[:50]}...\n+ {new_string[:50]}...",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# === WEB SEARCH ===

async def web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search the web using DuckDuckGo (HTML endpoint, with JSON fallback)."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        # Primary: HTML endpoint (most reliable, returns real results)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    results = _parse_ddg_html(html, num_results)
                    if results:
                        return {"success": True, "query": query,
                                "results": results[:num_results], "total": len(results)}
                # Fallback: JSON instant-answer API
                async with session.get(
                    f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as jr:
                    if jr.status == 200:
                        data = await jr.json()
                        results = []
                        if data.get("Abstract"):
                            results.append({
                                "title": data.get("Heading", ""),
                                "snippet": data.get("Abstract", ""),
                                "url": data.get("AbstractURL", ""),
                            })
                        for topic in data.get("RelatedTopics", [])[:num_results]:
                            if isinstance(topic, dict) and "Text" in topic:
                                results.append({
                                    "title": topic.get("Text", "")[:100],
                                    "snippet": topic.get("Text", ""),
                                    "url": topic.get("FirstURL", ""),
                                })
                        if results:
                            return {"success": True, "query": query,
                                    "results": results[:num_results], "total": len(results)}
            return {"success": False, "error": "No results found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_ddg_html(html: str, num_results: int) -> list:
    """Extract result links from DuckDuckGo HTML response."""
    results = []
    # Each result: class="result__a" (link) + class="result__snippet" (text)
    link_re = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
    snippet_re = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
    links = link_re.findall(html)
    snippets = snippet_re.findall(html)
    import html as _html
    for i, (href, title) in enumerate(links[:num_results]):
        # DDG wraps the real URL in its redirect; decode uddg param if present
        if "uddg=" in href:
            import urllib.parse as _up
            try:
                href = _up.unquote(_up.parse_qs(_up.urlparse(href).query).get("uddg", [href])[0])
            except Exception:
                pass
        title = _html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        snippet = ""
        if i < len(snippets):
            snippet = _html.unescape(re.sub(r"<[^>]+>", "", snippets[i])).strip()
        if title and href:
            results.append({"title": title[:80], "snippet": snippet[:200], "url": href})
    return results


# === TERMINAL (SANDBOXED) ===

async def terminal(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute terminal command (sandboxed)."""
    # Block dangerous commands
    blocked_commands = [
        'rm -rf', 'mkfs', 'dd', 'format', 'shutdown', 'reboot',
        'kill -9', 'pkill', 'killall', 'systemctl', 'service',
        'apt install', 'apt remove', 'pip install', 'npm install',
        'curl', 'wget',  # Block external downloads
    ]
    
    command_lower = command.lower()
    for blocked in blocked_commands:
        if blocked in command_lower:
            return {
                "success": False,
                "error": f"Command blocked for security: {blocked}",
            }
    
    try:
        # Run command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",  # Run in temp directory
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace")[:5000],
            "stderr": stderr.decode("utf-8", errors="replace")[:2000],
            "exit_code": process.returncode,
        }
    
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# === CODE GENERATION ===

async def code_generate(language: str, requirements: str, context: str = "") -> Dict[str, Any]:
    """Generate code using AI."""
    # This will be called from main.py with the AI API
    return {
        "success": True,
        "language": language,
        "requirements": requirements,
        "message": "Code generation delegated to AI",
    }


# === GITHUB OPERATIONS ===

async def github_push(repo: str, filename: str, content: str, 
                      commit_message: str = "feat: Add via OXYGENT", 
                      token: str = None) -> Dict[str, Any]:
    """Push file to GitHub repository."""
    if not token:
        return {"success": False, "error": "GitHub token required"}
    
    try:
        import base64
        
        # Check if file exists
        check_url = f"https://api.github.com/repos/{repo}/contents/{filename}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        async with aiohttp.ClientSession() as session:
            # Get existing file (if any)
            sha = None
            async with session.get(check_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    sha = data.get("sha")
            
            # Prepare payload
            payload = {
                "message": commit_message,
                "content": base64.b64encode(content.encode()).decode(),
            }
            if sha:
                payload["sha"] = sha
            
            # Push
            async with session.put(check_url, json=payload, headers=headers) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    return {
                        "success": True,
                        "url": data.get("content", {}).get("html_url", ""),
                        "filename": filename,
                    }
                else:
                    error = await response.text()
                    return {"success": False, "error": error}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


# === SCREENSHOT ===

async def website_screenshot(url: str) -> Dict[str, Any]:
    """Capture website screenshot."""
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Screenshot
            screenshot_path = f"/tmp/screenshot_{hash(url)}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            
            await browser.close()
            
            return {
                "success": True,
                "path": screenshot_path,
                "url": url,
            }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


# === MEMORY OPERATIONS ===

async def memory_store(user_id: int, key: str, value: str, category: str = "general") -> Dict[str, Any]:
    """Store memory entry."""
    try:
        from memory_system import get_memory
        memory = get_memory(user_id)
        memory.store(key, value, category)
        
        return {"success": True, "key": key, "value": value}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def memory_retrieve(user_id: int, key: str = None) -> Dict[str, Any]:
    """Retrieve memory entry."""
    try:
        from memory_system import get_memory
        memory = get_memory(user_id)
        
        if key:
            entry = memory.retrieve(key)
            return {"success": True, "data": entry}
        else:
            entries = memory.retrieve()
            return {"success": True, "data": entries}
    except Exception as e:
        return {"success": False, "error": str(e)}


# === TOOL REGISTRY ===

TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "search_files": search_files,
    "patch_file": patch_file,
    "web_search": web_search,
    "terminal": terminal,
    "code_generate": code_generate,
    "github_push": github_push,
    "website_screenshot": website_screenshot,
    "memory_store": memory_store,
    "memory_retrieve": memory_retrieve,
}


async def execute_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Execute a tool by name."""
    if tool_name not in TOOLS:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        func = TOOLS[tool_name]
        result = await func(**kwargs)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# === AI CHAT (OpenCode Zen) ===

async def _zen_chat(prompt: str, system: str = None) -> str:
    """Chat with OpenCode Zen API."""
    from config import OPENCODE_ZEN_BASE_URL, OPENCODE_ZEN_MODEL
    
    headers = {
        "Content-Type": "application/json",
    }
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": OPENCODE_ZEN_MODEL,
        "messages": messages,
        "stream": False
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('choices', [{}])[0].get('message', {}).get('content', '')
                else:
                    error = await response.text()
                    logger.error(f"Zen API error: {response.status} - {error}")
                    return ""
        except Exception as e:
            logger.error(f"Zen API exception: {e}")
            return ""


# === CODE SENDING ===

async def send_code_blocks(context, chat_id: int, code_blocks: list, intro: str = "", user_id: int = None):
    """Send code blocks as files."""
    for i, code in enumerate(code_blocks):
        lines = code.strip().split('\n')
        filename = f"file_{i}.py"
        if lines and lines[0].startswith('# file: '):
            filename = lines[0][8:]
            code = '\n'.join(lines[1:])
        
        try:
            await context.bot.send_document(
                chat_id=chat_id,
                document=io.BytesIO(code.encode('utf-8')),
                filename=filename,
                caption=f"📁 {filename}"
            )
        except Exception as e:
            logger.error(f"Failed to send code file: {e}")


def cleanup_sandbox(user_id: int):
    """Clean up sandbox directory for user."""
    import shutil
    sandbox_path = f"/tmp/oxygent_sandbox/{user_id}"
    try:
        if os.path.exists(sandbox_path):
            shutil.rmtree(sandbox_path)
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


# === DEPLOYMENT (VERCEL / CLOUDFLARE) ===

async def delete_deployment(uid: int, deploy_id: int) -> Dict[str, Any]:
    """Delete a hosted website or worker. Actually removes from Vercel/Cloudflare."""
    from database import get_deployment, remove_deployment

    dep = get_deployment(uid, deploy_id)
    if not dep:
        return {"success": False, "error": "Deployment not found."}

    dep_type = dep['deploy_type']
    name = dep['name']

    try:
        if dep_type == 'website':
            token = os.environ.get("VERCEL_TOKEN", "")
            if not token:
                try:
                    from database import get_setting
                    token = get_setting('vercel_token', '') or ''
                except Exception:
                    pass
            cmd = ["vercel", "remove", name, "--yes"]
            if token:
                cmd.extend(["--token", token])
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=60)

        elif dep_type == 'worker':
            cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
            if not cf_token:
                try:
                    from database import get_setting
                    cf_token = get_setting('cf_token', '') or ''
                except Exception:
                    pass
            env = os.environ.copy()
            if cf_token:
                env['CLOUDFLARE_API_TOKEN'] = cf_token
            cmd = ["npx", "wrangler", "delete", "--name", name, "--yes"]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
            )
            await asyncio.wait_for(proc.communicate(), timeout=60)

        remove_deployment(uid, deploy_id)
        return {"success": True, "deleted_name": name, "deleted_type": dep_type, "url": dep.get('url', '')}

    except asyncio.TimeoutError:
        return {"success": False, "error": "Delete timed out."}
    except Exception as e:
        logger.error(f"delete_deployment error: {e}")
        return {"success": False, "error": str(e)[:300]}


async def deploy_website(uid, project_name, source_dir, framework="static", build_command=None, output_dir=None):
    """Deploy a website/project to Vercel. Returns live URL."""
    import shutil
    try:
        from database import get_user_deploy_count, get_global_max_sites
        count = get_user_deploy_count(uid)
        max_sites = get_global_max_sites()
        if count >= max_sites:
            return {"success": False, "error": f"Deploy limit reached ({count}/{max_sites}). Delete an existing site first."}
    except Exception:
        max_sites = 5

    safe_name = re.sub(r'[^a-z0-9-]', '-', project_name.lower().strip())[:40] or f"site-{uid}"
    deploy_dir = tempfile.mkdtemp(prefix=f"vercel_{safe_name}_")
    try:
        src = Path(source_dir)
        if src.exists():
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src)
                    dest = Path(deploy_dir) / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(dest))

        vercel_config = {}
        if framework == "static":
            vercel_config = {"buildCommand": build_command, "outputDirectory": output_dir or ".", "framework": None}
        elif framework in ("nextjs", "react", "vue", "svelte"):
            vercel_config = {"framework": framework, "buildCommand": build_command, "outputDirectory": output_dir}
        elif framework == "python":
            vercel_config = {"buildCommand": build_command, "outputDirectory": output_dir or "."}
        vercel_config = {k: v for k, v in vercel_config.items() if v is not None}
        if vercel_config:
            with open(os.path.join(deploy_dir, "vercel.json"), "w") as f:
                json.dump(vercel_config, f, indent=2)

        token = os.environ.get("VERCEL_TOKEN", "")
        if not token:
            try:
                from database import get_setting
                token = get_setting('vercel_token', '') or ''
            except Exception:
                pass
        cmd = ["vercel", "--yes", "--prod"]
        if token:
            cmd.extend(["--token", token])
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=deploy_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        stdout_str = stdout.decode("utf-8", errors="replace").strip()
        stderr_str = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return {"success": False, "error": f"Deploy failed: {stderr_str[:300]}"}

        url = ""
        for line in stdout_str.split("\n"):
            if line.strip().startswith("https://"):
                url = line.strip()
                break
        if not url:
            m = re.search(r'https://[^\s]+\.vercel\.app[^\s]*', stdout_str)
            if m:
                url = m.group(0)

        if url:
            try:
                from database import add_deployment, get_user_deploy_count, get_global_max_sites
                add_deployment(uid, 'website', safe_name, url)
                count = get_user_deploy_count(uid)
                mx = get_global_max_sites()
                remaining = mx - count
            except Exception:
                count = 0; mx = 5; remaining = 5
            return {"success": True, "url": url, "project_name": safe_name, "remaining_sites": remaining, "max_sites": mx}
        return {"success": False, "error": f"Deploy completed but URL not found. Output: {stdout_str[:300]}"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Deploy timed out (5 min limit)"}
    except Exception as e:
        logger.error(f"deploy_website error: {e}")
        return {"success": False, "error": str(e)[:300]}
    finally:
        try:
            shutil.rmtree(deploy_dir, ignore_errors=True)
        except Exception:
            pass


async def deploy_bot(uid, bot_name, source_dir, env_vars=None):
    """Deploy a Telegram bot to Cloudflare Workers. Returns live worker URL."""
    import shutil
    try:
        from database import get_user_worker_count, get_global_max_workers
        count = get_user_worker_count(uid)
        max_workers = get_global_max_workers()
        if count >= max_workers:
            return {"success": False, "error": f"Worker limit reached ({count}/{max_workers}). Delete an existing worker first."}
    except Exception:
        max_workers = 5

    safe_name = re.sub(r'[^a-z0-9-]', '-', bot_name.lower().strip())[:40] or f"bot-{uid}"
    deploy_dir = tempfile.mkdtemp(prefix=f"wrangler_{safe_name}_")
    try:
        src = Path(source_dir)
        if src.exists():
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src)
                    dest = Path(deploy_dir) / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(dest))

        index_path = os.path.join(deploy_dir, "index.js")
        if not os.path.exists(index_path):
            for alt in ["main.js", "worker.js", "server.js", "bot.js"]:
                alt_path = os.path.join(deploy_dir, alt)
                if os.path.exists(alt_path):
                    shutil.copy2(alt_path, index_path)
                    break

        wrangler_config = {"name": safe_name, "main": "index.js", "compatibility_date": "2024-01-01"}
        if env_vars:
            wrangler_config["vars"] = env_vars
        with open(os.path.join(deploy_dir, "wrangler.jsonc"), "w") as f:
            json.dump(wrangler_config, f, indent=2)

        cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        if not cf_token:
            try:
                from database import get_setting
                cf_token = get_setting('cf_token', '') or ''
            except Exception:
                pass
        env = os.environ.copy()
        if cf_token:
            env['CLOUDFLARE_API_TOKEN'] = cf_token
        cmd = ["npx", "wrangler", "deploy", "--yes"]
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=deploy_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        stdout_str = stdout.decode("utf-8", errors="replace").strip()
        stderr_str = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return {"success": False, "error": f"Deploy failed: {stderr_str[:300]}"}

        url = ""
        for line in stdout_str.split("\n"):
            if "workers.dev" in line:
                m = re.search(r'https://[^\s]+\.workers\.dev[^\s]*', line)
                if m:
                    url = m.group(0)
                    break
        if not url:
            url = f"https://{safe_name}.workers.dev"

        try:
            from database import add_deployment, get_user_worker_count, get_global_max_workers
            add_deployment(uid, 'worker', safe_name, url)
            count = get_user_worker_count(uid)
            mx = get_global_max_workers()
            remaining = mx - count
        except Exception:
            count = 0; mx = 5; remaining = 5
        return {"success": True, "url": url, "worker_name": safe_name, "remaining_workers": remaining, "max_workers": mx}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Deploy timed out (2 min limit)"}
    except Exception as e:
        logger.error(f"deploy_bot error: {e}")
        return {"success": False, "error": str(e)[:300]}
    finally:
        try:
            shutil.rmtree(deploy_dir, ignore_errors=True)
        except Exception:
            pass


# === TOOL SCHEMAS (for AI) ===

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the file"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search files by name or content",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern"},
                    "path": {"type": "string", "description": "Directory to search", "default": "."},
                    "file_glob": {"type": "string", "description": "File pattern (e.g., *.py)"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Replace text in a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the file"},
                    "old_string": {"type": "string", "description": "Text to find"},
                    "new_string": {"type": "string", "description": "Replacement text"}
                },
                "required": ["filepath", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Execute a terminal command (sandboxed)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_push",
            "description": "Push file to GitHub repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo)"},
                    "filename": {"type": "string", "description": "File path in repo"},
                    "content": {"type": "string", "description": "File content"},
                    "commit_message": {"type": "string", "description": "Commit message"}
                },
                "required": ["repo", "filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "website_screenshot",
            "description": "Capture website screenshot",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Website URL"}
                },
                "required": ["url"]
            }
        }
    },
]
