"""
OXYCODE AI - Provider Management Module
=======================================
Handles AI provider validation, testing, selection, and fallback.
"""

import json
import logging
import asyncio
import aiohttp
from typing import Tuple, List, Optional, Dict, Any

import database as db

logger = logging.getLogger(__name__)

PROVIDER_DEFAULTS = {
    "opencode": {"base_url": "https://opencode.ai/zen/v1", "display_name": "OpenCode"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta", "display_name": "Gemini"},
    "nararouter": {"base_url": "https://router.bynara.id/v1", "display_name": "Nara Router"},
    "custom": {"base_url": "", "display_name": "Custom"},
}

OPENCODE_FREE_MODELS = [
    "x-preview-f-free",
    "mimo-v2.5-free", "deepseek-v4-flash-free", "hy3-free",
    "nemotron-3.5-lightning-free", "nemotron-3-ultra-free",
    "big-pickle", "laguna-s-2.1-free",
]

VALIDATION_TIMEOUT = 30


def _opencode_headers():
    """Headers for OpenCode Zen: Bearer key when configured, UA always."""
    import os
    headers = {"Content-Type": "application/json", "User-Agent": "opencode/1.18.16"}
    api_key = os.getenv("OPENCODE_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def validate_opencode(api_key=None, base_url=None):
    """Validate OpenCode — IP-based auth, no API key needed."""
    base = (base_url or PROVIDER_DEFAULTS["opencode"]["base_url"]).rstrip("/")
    url = base + "/chat/completions"
    payload = {"model": "mimo-v2.5-free", "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 10, "stream": False}
    headers = _opencode_headers()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=VALIDATION_TIMEOUT)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        models = await _fetch_opencode_free_models(base)
                        return True, models, ""
                    return False, [], "Invalid response format"
                else:
                    body = await resp.text()
                    return False, [], f"HTTP {resp.status}: {body[:200]}"
    except asyncio.TimeoutError:
        return False, [], "Connection timeout"
    except Exception as e:
        return False, [], f"Error: {str(e)[:200]}"


async def _fetch_opencode_free_models(base_url=None):
    """Fetch free models from OpenCode API."""
    base = (base_url or PROVIDER_DEFAULTS["opencode"]["base_url"]).rstrip("/")
    url = base + "/models"
    headers = _opencode_headers()
    headers.pop("Content-Type", None)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    all_models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
                    free_models = [m for m in all_models if m in OPENCODE_FREE_MODELS or "free" in m.lower()]
                    if not free_models:
                        free_models = OPENCODE_FREE_MODELS
                    return free_models
    except Exception as e:
        logger.error(f"Failed to fetch OpenCode models: {e}")
    return OPENCODE_FREE_MODELS


GEMINI_FREE_MODELS = [
    "gemini-2.5-flash", "gemini-2.5-flash-preview", "gemini-2.5-flash-lite",
    "gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash",
    "gemini-1.5-pro", "gemma-2-9b-it", "gemma-2-27b-it",
    "gemma-4-26b-a4b-it", "gemma-4-31b-it",
]


async def validate_gemini(api_key, base_url=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=VALIDATION_TIMEOUT)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    all_models = []
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        if name.startswith("models/"):
                            name = name[7:]
                        if name:
                            all_models.append(name)
                    # Filter to free models only
                    free_models = [m for m in all_models if m in GEMINI_FREE_MODELS]
                    if not free_models:
                        free_models = [m for m in all_models if "flash" in m.lower() and "preview" not in m.lower()]
                    if not free_models:
                        free_models = ["gemini-2.5-flash"]
                    return True, free_models, ""
                else:
                    body = await resp.text()
                    return False, [], f"HTTP {resp.status}: {body[:200]}"
                    return False, [], f"HTTP {resp.status}: {body[:200]}"
    except asyncio.TimeoutError:
        return False, [], "Connection timeout"
    except Exception as e:
        return False, [], f"Error: {str(e)[:200]}"


async def validate_custom(api_key, base_url):
    if not base_url:
        return False, [], "Base URL is required"
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        chat_url = base + "/v1/chat/completions"
    else:
        chat_url = base + "/chat/completions"
    payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 10, "stream": False}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(chat_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=VALIDATION_TIMEOUT)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "choices" in data:
                        models = await _fetch_models_list(base, api_key)
                        return True, models, ""
                    return False, [], "Invalid response format"
                else:
                    body = await resp.text()
                    return False, [], f"HTTP {resp.status}: {body[:200]}"
    except asyncio.TimeoutError:
        return False, [], "Connection timeout"
    except Exception as e:
        return False, [], f"Error: {str(e)[:200]}"


async def _fetch_models_list(base_url, api_key=None):
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        url = base + "/v1/models"
    else:
        url = base + "/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
                    return models[:50]
    except Exception:
        pass
    return []


async def validate_nararouter(api_key, base_url=None):
    base = (base_url or PROVIDER_DEFAULTS["nararouter"]["base_url"]).rstrip("/")
    chat_url = base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"
    # Use a confirmed FREE model for test
    payload = {"model": "qwen-3.8-max-free", "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 10, "stream": False}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(chat_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=VALIDATION_TIMEOUT)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        models = await _fetch_nararouter_free_models(api_key)
                        return True, models, ""
                    return False, [], "Invalid response format"
                else:
                    body = await resp.text()
                    return False, [], f"HTTP {resp.status}: {body[:200]}"
    except asyncio.TimeoutError:
        return False, [], "Connection timeout"
    except Exception as e:
        return False, [], f"Error: {str(e)[:200]}"


async def _fetch_nararouter_free_models(api_key=None):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://router.bynara.id/api/plans",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    plans = data if isinstance(data, list) else data.get("plans", data.get("data", []))
                    free_models = []
                    if isinstance(plans, list):
                        for plan in plans:
                            plan_code = str(plan.get("code", plan.get("name", ""))).lower()
                            plan_name = str(plan.get("name", "")).lower()
                            if "free" in plan_code and "freemium" not in plan_code:
                                models = plan.get("models", plan.get("available_models", []))
                                if isinstance(models, list):
                                    for m in models:
                                        if isinstance(m, str):
                                            free_models.append(m)
                                        elif isinstance(m, dict):
                                            free_models.append(m.get("id", m.get("name", "")))
                    if not free_models:
                        free_models = ["qwen-3.8-max-free", "agnes-2.5-flash", "mistral-medium-3-5", "ox-alpha", "stepfun-3.7-flash"]
                    return free_models
    except Exception as e:
        logger.error(f"Failed to fetch Nara Router models: {e}")
    return ["qwen-3.8-max-free", "agnes-2.5-flash", "mistral-medium-3-5", "ox-alpha", "stepfun-3.7-flash"]


async def validate_provider(provider_type, api_key=None, base_url=None):
    if provider_type == "opencode":
        return await validate_opencode(api_key, base_url)
    elif provider_type == "gemini":
        return await validate_gemini(api_key, base_url)
    elif provider_type == "nararouter":
        return await validate_nararouter(api_key, base_url)
    elif provider_type == "custom":
        return await validate_custom(api_key, base_url)
    else:
        return False, [], f"Unknown provider type: {provider_type}"


async def test_provider(provider_id):
    provider = db.get_provider(provider_id)
    if not provider:
        return {"ok": False, "models": [], "error": "Provider not found"}
    is_valid, models, error = await validate_provider(
        provider["provider_type"], provider.get("api_key", ""), provider.get("base_url"))
    models_json = json.dumps(models) if models else None
    db.update_provider_status(provider_id, is_working=1 if is_valid else 0,
        models_json=models_json, error_message=error if not is_valid else None)
    return {"ok": is_valid, "models": models, "error": error}


def get_provider_for_request():
    active = db.get_active_provider()
    if active and active.get("is_working"):
        return active
    working = db.get_working_providers()
    if working:
        return working[0]
    if active:
        return active
    return None


def get_provider_config(provider):
    provider_type = provider.get("provider_type", "custom")
    base_url = provider.get("base_url", "")
    api_key = provider.get("api_key", "")
    models_json = provider.get("models_json", "[]")
    try:
        models = json.loads(models_json) if models_json else []
    except (json.JSONDecodeError, TypeError):
        models = []
    if not base_url:
        base_url = PROVIDER_DEFAULTS.get(provider_type, {}).get("base_url", "")
    model = _select_best_model(provider_type, models)
    return {"base_url": base_url, "api_key": api_key, "model": model, "models": models, "provider_type": provider_type}


def _select_best_model(provider_type, models):
    if not models:
        if provider_type == "opencode":
            return "mimo-v2.5-free"
        elif provider_type == "gemini":
            return "gemini-2.5-flash"
        elif provider_type == "nararouter":
            return "qwen-3.8-max-free"
        return ""
    preferred = {
        "opencode": ["mimo-v2.5-free", "deepseek-v4-flash-free", "hy3-free", "big-pickle"],
        "gemini": ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite"],
        "nararouter": ["qwen-3.8-max-free", "agnes-2.5-flash", "mistral-medium-3-5", "ox-alpha"],
    }
    for pref in preferred.get(provider_type, []):
        for m in models:
            if pref.lower() in m.lower():
                return m
    return models[0]


def get_opencode_config():
    """Return OpenCode IP-based config (no API key needed)."""
    return {
        "base_url": PROVIDER_DEFAULTS["opencode"]["base_url"],
        "api_key": "",
        "model": "mimo-v2.5-free",
        "models": OPENCODE_FREE_MODELS,
        "provider_type": "opencode",
    }
