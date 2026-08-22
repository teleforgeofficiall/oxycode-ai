"""
OXYCODE AI — Cloudflare Deployment
===================================

Deploys user projects to Cloudflare Pages and Workers
using the user's connected Cloudflare account.

Deployment Flow:
1. User builds project → files are ready
2. Call Cloudflare Pages API to create/update project
3. Upload files as a deployment
4. Return the live URL

Cloudflare Pages API:
- POST /accounts/{account_id}/pages/projects — Create project
- POST /accounts/{account_id}/pages/projects/{project_name}/deployments — Deploy
- Upload files as multipart/form-data

Cloudflare Workers API:
- PUT /accounts/{account_id}/workers/scripts/{script_name} — Upload script
- PUT /accounts/{account_id}/workers/scripts/{script_name}/settings — Update settings
"""

import os
import json
import hashlib
import zipfile
import io
import logging
from typing import Dict, List, Optional
from datetime import datetime

import aiohttp

from cloudflare_oauth import cf_api_get, cf_api_post, cf_api_put, get_cloudflare_account

logger = logging.getLogger(__name__)

# ==================== PAGES DEPLOYMENT ====================

async def deploy_to_pages(
    telegram_id: int,
    project_name: str,
    files: Dict[str, str],
    branch: str = "main",
) -> Dict:
    """Deploy files to Cloudflare Pages.
    
    Args:
        telegram_id: User's Telegram ID (to get their CF token)
        project_name: Name for the Pages project (sanitized)
        files: Dict of {filepath: content} to deploy
        branch: Branch name (default: main)
        
    Returns:
        {
            "success": True,
            "url": "https://xxx.pages.dev",
            "project_name": str,
            "deployment_id": str,
        }
    """
    account = get_cloudflare_account(telegram_id)
    if not account:
        raise ValueError("Cloudflare account not connected")
    
    account_id = account["account_id"]
    if not account_id:
        raise ValueError("No Cloudflare account ID found")
    
    # Sanitize project name (Cloudflare requirement: lowercase, alphanumeric + hyphens)
    sanitized_name = _sanitize_project_name(project_name)
    
    # Step 1: Create or get project
    project = await _ensure_pages_project(telegram_id, account_id, sanitized_name)
    
    # Step 2: Create deployment with files
    deployment = await _create_pages_deployment(
        telegram_id, account_id, sanitized_name, files, branch
    )
    
    # Build the URL
    url = f"https://{sanitized_name}.pages.dev"
    
    return {
        "success": True,
        "url": url,
        "projectName": sanitized_name,
        "deploymentId": deployment.get("id"),
        "status": deployment.get("status"),
    }


async def _ensure_pages_project(
    telegram_id: int, account_id: str, project_name: str
) -> Dict:
    """Create a Pages project if it doesn't exist."""
    # Try to get existing project
    try:
        result = await cf_api_get(
            telegram_id,
            f"/accounts/{account_id}/pages/projects/{project_name}"
        )
        if result.get("success"):
            return result["result"]
    except Exception:
        pass
    
    # Create new project
    result = await cf_api_post(
        telegram_id,
        f"/accounts/{account_id}/pages/projects",
        data={
            "name": project_name,
            "production_branch": "main",
        }
    )
    
    if not result.get("success"):
        errors = result.get("errors", [])
        raise ValueError(f"Failed to create Pages project: {errors}")
    
    return result["result"]


async def _create_pages_deployment(
    telegram_id: int,
    account_id: str,
    project_name: str,
    files: Dict[str, str],
    branch: str,
) -> Dict:
    """Create a deployment with the given files."""
    account = get_cloudflare_account(telegram_id)
    
    # Create a zip of all files
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in files.items():
            zf.writestr(filepath, content)
    zip_buffer.seek(0)
    
    # Upload as multipart form
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{project_name}/deployments"
    
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            zip_buffer,
            filename="deploy.zip",
            content_type="application/zip",
        )
        form.add_field("branch", branch)
        
        async with session.post(
            url,
            headers={"Authorization": f"Bearer {account['api_token']}"},
            data=form,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            result = await resp.json()
            
            if not result.get("success"):
                errors = result.get("errors", [])
                raise ValueError(f"Deployment failed: {errors}")
            
            return result["result"]


# ==================== WORKERS DEPLOYMENT ====================

async def deploy_to_workers(
    telegram_id: int,
    script_name: str,
    script_content: str,
    bindings: Dict = None,
) -> Dict:
    """Deploy a Worker script.
    
    Args:
        telegram_id: User's Telegram ID
        script_name: Name for the Worker (sanitized)
        script_content: JavaScript/TypeScript source code
        bindings: Optional KV/D1/R2 bindings
        
    Returns:
        {
            "success": True,
            "url": "https://xxx.workers.dev",
            "script_name": str,
        }
    """
    account = get_cloudflare_account(telegram_id)
    if not account:
        raise ValueError("Cloudflare account not connected")
    
    account_id = account["account_id"]
    if not account_id:
        raise ValueError("No Cloudflare account ID found")
    
    # Sanitize script name
    sanitized_name = _sanitize_worker_name(script_name)
    
    # Upload the script
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{sanitized_name}"
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {account['api_token']}",
            "Content-Type": "application/javascript",
        }
        
        async with session.put(
            url,
            headers=headers,
            data=script_content.encode("utf-8"),
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            result = await resp.json()
            
            if not result.get("success"):
                errors = result.get("errors", [])
                raise ValueError(f"Worker deployment failed: {errors}")
    
    # Update settings if bindings provided
    if bindings:
        await _update_worker_settings(telegram_id, account_id, sanitized_name, bindings)
    
    # Enable the worker on a subdomain
    subdomain = await _get_worker_subdomain(telegram_id, account_id)
    
    return {
        "success": True,
        "url": f"https://{sanitized_name}.{subdomain}.workers.dev",
        "scriptName": sanitized_name,
    }


async def _update_worker_settings(
    telegram_id: int, account_id: str, script_name: str, bindings: Dict
):
    """Update Worker settings with bindings."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}/settings"
    
    settings = {}
    if bindings.get("kv_namespaces"):
        settings["bindings"] = [
            {"name": b["name"], "namespace_id": b["namespace_id"]}
            for b in bindings["kv_namespaces"]
        ]
    
    await cf_api_put(telegram_id, url, data=settings)


async def _get_worker_subdomain(telegram_id: int, account_id: str) -> str:
    """Get the account's workers.dev subdomain."""
    result = await cf_api_get(
        telegram_id,
        f"/accounts/{account_id}/workers/subdomain"
    )
    if result.get("success"):
        return result["result"].get("subdomain", "workers.dev")
    return "workers.dev"


# ==================== HELPERS ====================

def _sanitize_project_name(name: str) -> str:
    """Sanitize a name for Cloudflare Pages (lowercase, alphanumeric + hyphens)."""
    # Remove invalid characters
    sanitized = name.lower().strip()
    sanitized = "".join(c if c.isalnum() or c == "-" else "-" for c in sanitized)
    # Remove consecutive hyphens
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip("-")
    # Ensure it starts with a letter
    if sanitized and not sanitized[0].isalpha():
        sanitized = "app-" + sanitized
    return sanitized or "my-app"


def _sanitize_worker_name(name: str) -> str:
    """Sanitize a name for Cloudflare Workers."""
    return _sanitize_project_name(name)


def generate_worker_script(
    html_content: str,
    js_content: str = "",
    css_content: str = "",
) -> str:
    """Generate a Cloudflare Worker script that serves static HTML.
    
    This creates a simple Worker that returns the HTML content.
    Use this for deploying static sites as Workers.
    """
    # Escape content for JavaScript strings
    html_escaped = html_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    js_escaped = js_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${") if js_content else ""
    css_escaped = css_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${") if css_content else ""
    
    script = f"""
addEventListener('fetch', event => {{
  event.respondWith(handleRequest(event.request))
}})

async function handleRequest(request) {{
  const html = `{html_escaped}`
  
  const response = new Response(html, {{
    headers: {{
      'Content-Type': 'text/html;charset=UTF-8',
      'Cache-Control': 'no-cache',
    }},
  }})
  
  return response
}}
"""
    return script.strip()


def generate_pages_files(
    html_content: str,
    css_content: str = "",
    js_content: str = "",
    assets: Dict[str, str] = None,
) -> Dict[str, str]:
    """Generate files for a Cloudflare Pages deployment.
    
    Returns dict of {filepath: content} for all files.
    """
    files = {
        "index.html": html_content,
    }
    
    if css_content:
        files["style.css"] = css_content
    
    if js_content:
        files["script.js"] = js_content
    
    if assets:
        files.update(assets)
    
    return files
