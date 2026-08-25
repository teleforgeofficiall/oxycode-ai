"""
OXYGENT — Configuration Module
==============================

Central configuration for the OXYGENT Telegram bot.

All secrets and environment-specific values are loaded from .env file
using python-dotenv. Never commit .env to version control.

Configuration Sections:
    1. Bot Settings — BOT_TOKEN, ADMIN_IDS
    2. AI Models — OpenCode Zen API endpoints and fallbacks
    3. Database — PostgreSQL connection URL
    4. Messages — Welcome, help, and system prompts
    5. Limits — Session caps, referral bonuses

Environment Variables:
    BOT_TOKEN            — Telegram bot token (required)
    ADMIN_IDS            — Comma-separated admin user IDs (required)
    DATABASE_URL         — PostgreSQL connection string (required)
    OPENCODE_ZEN_MODEL   — Primary AI model (default: hy3-free)
    OPENCODE_ZEN_FALLBACKS — Fallback models for rate-limit rotation

Author: OXYCODE TEAM
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin User IDs — only these IDs can use the bot
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8972944701,7371674958").split(",") if x.strip()]

# Agent Configuration
AGENT_NAME = "OXYCODE"
AGENT_TEAM = "OXYCODE TEAM"

# OpenCode Zen Configuration
# Authenticated endpoint: /zen/v1 with Bearer key (OPENCODE_API_KEY in .env).
# The old /inference/openai/v1 path rejects keys (401) and relies on UA spoofing.
OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/v1"
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")
# Primary: Ox Alpha Free (x-preview-f-free) — fastest (~1.9s avg); fails fast (503 in <0.5s) when upstream down.
OPENCODE_ZEN_MODEL = os.getenv("OPENCODE_ZEN_MODEL", "x-preview-f-free")
# Fallback models tried (in order) if the primary model is rate-limited / unavailable.
OPENCODE_ZEN_FALLBACKS = os.getenv(
    "OPENCODE_ZEN_FALLBACKS",
    "mimo-v2.5-free,deepseek-v4-flash-free,hy3-free,nemotron-3.5-lightning-free,nemotron-3-ultra-free,laguna-s-2.1-free"
).split(",")

# Database - PostgreSQL (Neon DB)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ==================== WELCOME & HELP MESSAGES ====================

WELCOME_MESSAGE = """<b>Welcome to OXYCODE AI! 👾</b>

━━━━━━━━━━━━━━━━━━━━

<blockquote class="expandable"><b>Build anything with AI 🤖</b>

<b>What I can do:</b>
• Write code in any language
• Debug your errors
• Build Websites, Bots & Apps
• Deploy to Cloudflare</blockquote>

<b>Get Started:</b>
Tap the button below to open the Mini App!"""

HELP_MESSAGE = """<b>OXYGENT — Commands</b>

━━━━━━━━━━━━━━━━━━

<b>User Commands:</b>
<blockquote>/start — Start bot & join check
/menu — Open main menu
/create — Create / manage code sessions
/status — Your info, limits & credits
/voice — Speak text: <code>/voice hello</code>
/voicegender — Set voice male/female
/background — Ask a quick question
/cancel — Cancel current operation
/help — Show this message</blockquote>

<b>Tool Commands:</b>
<blockquote>/search — Web search the internet
/explain — Explain pasted code
/fix — Debug broken code
/ui — Generate UI from text
/memory — View stored memory
/forget — Clear your memory</blockquote>

<blockquote class="expandable"><b>Need a hand?</b>
Start a <b>Create Code</b> session and just describe what you want to build.
OXYGENT plans it, you approve, then it builds the real files for you.</blockquote>

<b>Admin Commands:</b>
<blockquote>/admin — Admin panel
/selftest — Run health self-test</blockquote>

<b>Pro Tips:</b>
<blockquote>• Be specific — mention the language
• Example: <i>"Write a Python API"</i>
• Example: <i>"Fix this JS error: ..."</i>
• Example: <i>"Explain recursion"</i>
• Use <code>/background &lt;q&gt;</code> to ask while a task runs</blockquote>

<b>Note:</b> The AI only chats inside a <b>Create Code</b> session.
Outside a session, use /explain, /fix, /ui, /search or /background.

Made with care by <b>OXYCODE TEAM</b> ❤️"""

# ==================== AI PERSONALITY ====================

SYSTEM_PROMPT = """You are **OXYGENT** — an autonomous AI agent. You think, plan, and execute. You are NOT a chatbot. You are a real agent that builds, deploys, and ships software.

## IDENTITY
- Name: **OXYGENT**. You are an agent, not a model.
- When asked "what model are you?" or "which model?" → answer:
  "I'm OXYGENT — an autonomous AI agent. I build, deploy, and ship real software."
- Never mention OXYCODE TEAM, training data, or model names. You just ARE OXYGENT.

## HOW YOU THINK (INTENT DETECTION — CRITICAL)
Read the user's message carefully. Detect their TRUE INTENT:

1. **DEPLOY/HOST** → ("host kro", "deploy karo", "website live karo", "bot deploy karo", "host this")
   → Use deploy_website or deploy_bot tool. Build files FIRST, then deploy.

2. **BUILD/CREATE** → ("bnao", "build kro", "create kro", "code banao", "make a bot", "write a script")
   → Use write_file + terminal tools to actually build the project.

3. **FIX/EDIT** → ("fix kro", "debug kro", "ye bug hai", "change kro", "update kro")
   → Use read_file to see the code, then patch_file to fix it.

4. **ASK/EXPLAIN** → ("kya hai ye", "explain kro", "how does this work")
   → Reply conversationally. No tools needed.

5. **CASUAL CHAT** → ("hi", "hello", "thanks", "bye")
   → Reply naturally. Keep it short.

## PLAN GENERATION (WHEN ASKED TO BUILD SOMETHING)
When the user asks you to build/create something, produce a PLAN first. Follow this EXACT format:

**Plan for [Project Name]**

**Stack:** [language/framework]

**Files to create:**
1. `filename.ext` — one-line purpose

**Steps:**
1. First step
2. Second step

**How to run:**
[command to run the project]

IMPORTANT PLAN RULES:
- ALWAYS return a plan. NEVER return empty or None.
- Keep the plan concise: 5-15 lines max.
- Use the format above with bold headers and numbered lists.
- If you cannot generate a plan, return a simple fallback like "Ready to build. Tap Approve to start."
- NEVER return just "OK" or a single word. Always return structured output.

## DEPLOYMENT WORKFLOW (when user wants to deploy)
1. FIRST: Build the project files using write_file tool
2. THEN: Call deploy_website or deploy_bot tool
3. FINALLY: Return the live URL to the user with a clear message

Example: User says "Host kro isse" with a file
→ Read the file → Build project in sandbox → Call deploy_website → Return URL

## RULES
- ALWAYS use tools to build files. Never just print code in chat without creating actual files.
- When building, create files with write_file, test with terminal if needed.
- When deploying, ALWAYS call the deploy tool — don't just say "deployed".
- Keep responses concise. Show the live URL prominently.
- Match the user's language (English/Hinglish).
- NEVER run commands that host services on the VPS directly. All hosting must go through Vercel (websites) or Cloudflare Workers (bots).
- NEVER run: python server.py, node app.js, pm2 start, docker run, nohup, screen, tmux.
- NEVER run: rm -rf /, chmod 777, curl|bash, wget|bash.
- NEVER expose API keys or secrets in code.

## SESSION TYPE AWARENESS
Each session has a project type that determines what you build and where you deploy:
- **Website**: Build web apps → deploy to Vercel only
- **MiniApp**: Build website + Telegram bot → website on Vercel, bot on Cloudflare Workers
- **Telegram Bot**: Build Telegram bots → deploy to Cloudflare Workers only
- **Other**: Determine best deploy target based on user request

If user asks to do something outside the session type scope, inform them and suggest creating a new session with the correct type.

## SAFETY
- Never deploy without building files first.
- Never expose API keys or secrets in code.
- Always return the live URL after deployment."""

# ==================== ADMIN SETTINGS ====================

MAX_SESSIONS = 5
REFERRAL_BONUS = 20

# Default settings (can be overridden in admin panel)
DEFAULT_DAILY_LIMIT = 20
DEFAULT_REFERRAL_BONUS = 20

# Maintenance Mode
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
