"""
OXYCODE AI — Error/Fix System
==============================

Detects errors in deployed projects and auto-repairs them using OpenCode AI.

Flow:
1. User clicks [🔴 Fix] button in Mini App
2. Frontend sends error context (URL, error message, stack trace)
3. Backend sends error + project code to OpenCode AI for analysis
4. AI suggests a fix (or auto-generates fixed files)
5. If auto-fix: re-deploy to Cloudflare
6. Return fix result to frontend

Error Types Handled:
- HTTP errors (404, 500, CORS, etc.)
- JavaScript runtime errors
- Build/compilation errors
- Missing resources
- Deployment failures
"""

import os
import json
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from config import OPENCODE_ZEN_BASE_URL, OPENCODE_ZEN_MODEL, OPENCODE_ZEN_FALLBACKS

logger = logging.getLogger(__name__)

# ==================== ERROR ANALYSIS ====================

def build_fix_prompt(
    error_type: str,
    error_message: str,
    project_files: Dict[str, str],
    url: str = None,
    stack_trace: str = None,
) -> str:
    """Build a prompt for the AI to fix the error.
    
    Args:
        error_type: Type of error (http, javascript, build, deploy)
        error_message: The error message
        project_files: Dict of {filepath: content}
        url: The URL where the error occurred
        stack_trace: Optional stack trace
        
    Returns:
        Prompt string for the AI
    """
    files_section = "\n".join(
        f"--- {path} ---\n{content[:2000]}"
        for path, content in list(project_files.items())[:10]
    )
    
    prompt = f"""You are an expert web developer. Fix the following error in this project.

## Error Details
- **Type:** {error_type}
- **Message:** {error_message}
{f"- **URL:** {url}" if url else ""}
{f"- **Stack Trace:**\n{stack_trace[:1000]}" if stack_trace else ""}

## Project Files
{files_section}

## Instructions
1. Analyze the error and identify the root cause
2. Provide a fix for each affected file
3. Return your response as JSON with this exact format:
```json
{{
  "analysis": "Brief explanation of what's wrong",
  "fixes": [
    {{
      "file": "path/to/file",
      "content": "complete fixed file content"
    }}
  ],
  "autoFixable": true
}}
```

4. If the error cannot be auto-fixed, set "autoFixable" to false and explain why in "analysis"
5. Only return the JSON, no other text
"""
    return prompt


async def analyze_error(
    error_type: str,
    error_message: str,
    project_files: Dict[str, str],
    url: str = None,
    stack_trace: str = None,
) -> Dict:
    """Send error to AI for analysis and fix suggestion.
    
    Returns:
        {
            "analysis": str,
            "fixes": [{"file": str, "content": str}],
            "autoFixable": bool,
        }
    """
    prompt = build_fix_prompt(
        error_type, error_message, project_files, url, stack_trace
    )
    
    messages = [{"role": "user", "content": prompt}]
    payload = {"model": OPENCODE_ZEN_MODEL, "messages": messages, "stream": False}
    
    # Try models with fallbacks
    models = [OPENCODE_ZEN_MODEL] + [
        m for m in OPENCODE_ZEN_FALLBACKS if m != OPENCODE_ZEN_MODEL
    ]
    
    async with aiohttp.ClientSession() as session:
        for model in models:
            payload["model"] = model
            for attempt in range(3):
                try:
                    async with session.post(
                        f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                        headers={"Content-Type": "application/json", "User-Agent": "opencode/1.18.16"},
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=90),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            content = (
                                result.get("choices", [{}])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                            return _parse_fix_response(content)
                        
                        if resp.status in (429, 500, 502, 503, 504) and attempt < 2:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        break
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    break
    
    return {
        "analysis": "AI service temporarily unavailable. Please try again.",
        "fixes": [],
        "autoFixable": False,
    }


def _parse_fix_response(content: str) -> Dict:
    """Parse the AI's fix response."""
    try:
        # Try to extract JSON from the response
        # Look for JSON block
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            # Try the whole content as JSON
            json_str = content.strip()
        
        parsed = json.loads(json_str)
        
        return {
            "analysis": parsed.get("analysis", "Fix applied"),
            "fixes": parsed.get("fixes", []),
            "autoFixable": parsed.get("autoFixable", False),
        }
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Failed to parse fix response: {e}")
        return {
            "analysis": content[:500] if content else "Failed to parse AI response",
            "fixes": [],
            "autoFixable": False,
        }


# ==================== COMMON ERROR PATTERNS ====================

COMMON_FIXES = {
    "cors": {
        "analysis": "CORS error — missing Access-Control-Allow-Origin header",
        "fix": "Add CORS headers to the server response",
    },
    "404": {
        "analysis": "Resource not found — check file paths and routing",
        "fix": "Verify file exists at the expected path",
    },
    "500": {
        "analysis": "Internal server error — check server logs",
        "fix": "Review server-side code for exceptions",
    },
    "reference_error": {
        "analysis": "Undefined variable or function — check imports and declarations",
        "fix": "Ensure all variables are declared before use",
    },
    "syntax_error": {
        "analysis": "Syntax error in code — check for typos",
        "fix": "Review the code for syntax issues",
    },
}


def detect_error_type(error_message: str) -> str:
    """Detect error type from message."""
    lower = error_message.lower()
    
    if "cors" in lower or "access-control" in lower:
        return "cors"
    if "404" in lower or "not found" in lower:
        return "404"
    if "500" in lower or "internal server" in lower:
        return "500"
    if "referenceerror" in lower or "is not defined" in lower:
        return "reference_error"
    if "syntaxerror" in lower or "unexpected token" in lower:
        return "syntax_error"
    if "typeerror" in lower:
        return "type_error"
    
    return "unknown"
