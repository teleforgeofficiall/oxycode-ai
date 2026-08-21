"""
OXYCODE AI — Project Analyzer
==============================

Auto-detects project type, tech stack, and deployment target from a user prompt.
Uses keyword matching and heuristics (no AI call needed — fast and free).
"""

import re
from typing import Dict, List, Optional


def analyze_prompt(prompt: str) -> Dict:
    """Analyze a build prompt and return project type, tech stack, and deployment info.
    
    Returns:
        {
            "projectType": str,       # website, telegram-bot, miniapp, api, desktop-app, library, script
            "techStack": list[str],   # e.g. ["react", "typescript", "tailwind"]
            "deploymentTarget": str,  # cloudflare-pages, cloudflare-workers, vercel, none
            "files": list[str],       # suggested file structure
            "runCommand": str,        # command to run the project
            "description": str,       # one-line description
        }
    """
    lower = prompt.lower()
    
    # Detect project type
    project_type = _detect_project_type(lower)
    
    # Detect tech stack
    tech_stack = _detect_tech_stack(lower, project_type)
    
    # Determine deployment target
    deployment = _detect_deployment_target(project_type, tech_stack)
    
    # Generate file structure
    files = _generate_file_structure(project_type, tech_stack)
    
    # Generate run command
    run_cmd = _generate_run_command(project_type, tech_stack)
    
    return {
        "projectType": project_type,
        "techStack": tech_stack,
        "deploymentTarget": deployment,
        "files": files,
        "runCommand": run_cmd,
        "description": _generate_description(project_type, tech_stack, prompt),
    }


def _detect_project_type(lower: str) -> str:
    """Detect the primary project type from the prompt."""
    
    # Telegram Bot
    if any(kw in lower for kw in [
        "telegram bot", "tg bot", "telebot", "pyrogram", "aiogram",
        "python-telegram-bot", "botfather", "telegram bot"
    ]):
        return "telegram-bot"
    
    # Mini App (Telegram Web App)
    if any(kw in lower for kw in [
        "mini app", "miniapp", "web app", "telegram webapp",
        "telegram mini app", "webapp"
    ]):
        return "miniapp"
    
    # API / Backend
    if any(kw in lower for kw in [
        "api", "backend", "server", "rest", "graphql", "fastapi",
        "express", "flask", "django", "endpoint", "microservice"
    ]):
        return "api"
    
    # Desktop App
    if any(kw in lower for kw in [
        "desktop app", "electron", "tauri", "gui app", "desktop application",
        "windows app", "mac app", "linux app"
    ]):
        return "desktop-app"
    
    # Library / Package
    if any(kw in lower for kw in [
        "library", "package", "module", "npm package", "pip package",
        "sdk", "toolkit", "framework"
    ]):
        return "library"
    
    # Script / CLI
    if any(kw in lower for kw in [
        "script", "cli", "command line", "terminal", "automation",
        "scraper", "crawler", "bot script"
    ]):
        return "script"
    
    # Default: Website
    return "website"


def _detect_tech_stack(lower: str, project_type: str) -> List[str]:
    """Detect the tech stack from the prompt."""
    stack = []
    
    # Frontend frameworks
    if any(kw in lower for kw in ["react", "jsx", "tsx", "nextjs", "next.js"]):
        stack.append("react")
    if any(kw in lower for kw in ["vue", "nuxt", "nuxtjs"]):
        stack.append("vue")
    if any(kw in lower for kw in ["svelte", "sveltekit"]):
        stack.append("svelte")
    if any(kw in lower for kw in ["angular"]):
        stack.append("angular")
    
    # Backend frameworks
    if any(kw in lower for kw in ["fastapi", "fast api"]):
        stack.append("fastapi")
    if any(kw in lower for kw in ["express", "expressjs"]):
        stack.append("express")
    if any(kw in lower for kw in ["flask"]):
        stack.append("flask")
    if any(kw in lower for kw in ["django"]):
        stack.append("django")
    if any(kw in lower for kw in ["nest", "nestjs"]):
        stack.append("nestjs")
    
    # Languages
    if any(kw in lower for kw in ["python", "py"]):
        stack.append("python")
    if any(kw in lower for kw in ["typescript", "ts"]):
        stack.append("typescript")
    if any(kw in lower for kw in ["javascript", "js"]):
        stack.append("javascript")
    if any(kw in lower for kw in ["golang", "go "]):
        stack.append("go")
    if any(kw in lower for kw in ["rust", "rs"]):
        stack.append("rust")
    if any(kw in lower for kw in ["dart", "flutter"]):
        stack.append("dart")
    
    # Styling
    if any(kw in lower for kw in ["tailwind", "tailwindcss"]):
        stack.append("tailwind")
    if any(kw in lower for kw in ["bootstrap"]):
        stack.append("bootstrap")
    if any(kw in lower for kw in ["chakra"]):
        stack.append("chakra")
    
    # Database
    if any(kw in lower for kw in ["postgres", "postgresql", "psql"]):
        stack.append("postgresql")
    if any(kw in lower for kw in ["mysql"]):
        stack.append("mysql")
    if any(kw in lower for kw in ["mongodb", "mongo"]):
        stack.append("mongodb")
    if any(kw in lower for kw in ["redis"]):
        stack.append("redis")
    if any(kw in lower for kw in ["sqlite"]):
        stack.append("sqlite")
    
    # Telegram
    if any(kw in lower for kw in ["telegram", "pyrogram", "aiogram"]):
        stack.append("telegram")
    
    # Default stacks based on project type
    if not stack:
        if project_type == "website":
            stack = ["react", "typescript", "tailwind"]
        elif project_type == "telegram-bot":
            stack = ["python", "telegram"]
        elif project_type == "api":
            stack = ["python", "fastapi"]
        elif project_type == "miniapp":
            stack = ["react", "typescript", "tailwind", "telegram"]
        elif project_type == "desktop-app":
            stack = ["typescript"]
        elif project_type == "library":
            stack = ["typescript"]
        elif project_type == "script":
            stack = ["python"]
    
    return stack


def _detect_deployment_target(project_type: str, tech_stack: List[str]) -> str:
    """Determine the best deployment target."""
    
    # Telegram bots → Cloudflare Workers
    if project_type == "telegram-bot":
        return "cloudflare-workers"
    
    # Mini apps → Cloudflare Pages (frontend) + Workers (bot)
    if project_type == "miniapp":
        return "cloudflare-pages"
    
    # Websites → Cloudflare Pages
    if project_type == "website":
        return "cloudflare-pages"
    
    # APIs → Cloudflare Workers
    if project_type == "api":
        if "python" in tech_stack:
            return "vercel"  # Python APIs better on Vercel
        return "cloudflare-workers"
    
    # Desktop apps → no cloud deployment
    if project_type == "desktop-app":
        return "none"
    
    # Libraries → no cloud deployment
    if project_type == "library":
        return "none"
    
    # Scripts → no cloud deployment
    if project_type == "script":
        return "none"
    
    return "cloudflare-pages"


def _generate_file_structure(project_type: str, tech_stack: List[str]) -> List[str]:
    """Generate a suggested file structure."""
    
    if project_type == "website" or project_type == "miniapp":
        if "react" in tech_stack or "vue" in tech_stack:
            return [
                "index.html",
                "src/main.tsx",
                "src/App.tsx",
                "src/components/Header.tsx",
                "src/components/Hero.tsx",
                "src/styles/globals.css",
                "package.json",
                "vite.config.ts",
                "tsconfig.json",
                "tailwind.config.js",
            ]
        return [
            "index.html",
            "style.css",
            "script.js",
            "package.json",
        ]
    
    if project_type == "telegram-bot":
        if "python" in tech_stack:
            return [
                "bot.py",
                "config.py",
                "requirements.txt",
                ".env",
                "README.md",
            ]
        return [
            "bot.js",
            "config.js",
            "package.json",
            ".env",
            "README.md",
        ]
    
    if project_type == "api":
        if "python" in tech_stack:
            return [
                "main.py",
                "requirements.txt",
                ".env",
                "README.md",
            ]
        return [
            "src/index.ts",
            "package.json",
            "tsconfig.json",
            ".env",
            "README.md",
        ]
    
    if project_type == "script":
        return [
            "script.py",
            "requirements.txt",
            "README.md",
        ]
    
    return [
        "index.html",
        "package.json",
        "README.md",
    ]


def _generate_run_command(project_type: str, tech_stack: List[str]) -> str:
    """Generate the command to run the project."""
    
    if project_type in ("website", "miniapp"):
        if "react" in tech_stack or "vue" in tech_stack:
            return "npm run dev"
        return "npx serve ."
    
    if project_type == "telegram-bot":
        if "python" in tech_stack:
            return "python bot.py"
        return "node bot.js"
    
    if project_type == "api":
        if "python" in tech_stack:
            return "uvicorn main:app --reload"
        return "npm run dev"
    
    if project_type == "script":
        return "python script.py"
    
    return "npm run dev"


def _generate_description(project_type: str, tech_stack: List[str], prompt: str) -> str:
    """Generate a one-line description."""
    stack_str = " + ".join(tech_stack[:3])
    type_map = {
        "website": "Website",
        "telegram-bot": "Telegram Bot",
        "miniapp": "Mini App",
        "api": "API",
        "desktop-app": "Desktop App",
        "library": "Library",
        "script": "Script",
    }
    type_name = type_map.get(project_type, "Project")
    return f"{type_name} built with {stack_str}"
