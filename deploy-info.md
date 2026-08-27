# OXYCODE AI - Deployment Guide

## Project Overview
- **Name**: OXYCODE AI — Telegram Mini App VibeCoding Agent
- **Stack**: React (Vite) + Cloudflare Pages (frontend) + Python FastAPI (VPS backend) + Neon PostgreSQL
- **Frontend URL**: https://oxycode-miniapp.pages.dev
- **Backend URL**: https://oxycode.duckdns.org
- **Telegram Bot**: @OXYCODE_AI_BOT

---

## Prerequisites

### 1. GitHub Repository
- **Repo**: https://github.com/teleforgeofficiall/oxycode-ai.git
- **PAT Token**: `$GITHUB_PAT` (stored in VPS .prod.vars)

### 2. VPS (Backend Server)
- **IP**: `YOUR_VPS_IP`
- **User**: `root`
- **Password**: `$VPS_PASSWORD` (use SSH key auth)
- **OS**: Linux (Debian/Ubuntu)
- **Services**:
  - `oxycode-bot.service` — Telegram bot (runs `main.py`)
  - `oxycode-api.service` — FastAPI backend on port 8000 (runs `api_server.py`)
- **Path**: `/root/oxycode-bot/`

### 3. Neon Database (PostgreSQL)
- **Connection String**:
  ```
  $DATABASE_URL
  ```
- **Tables**: `chats`, `users`, `messages`, etc.
- **Important Column**: `chats.agent_type TEXT DEFAULT 'oxygent'`

### 4. DuckDNS Domain
- **Domain**: `oxycode.duckdns.org`
- **Token**: `$DUCKDNS_TOKEN`
- **SSL**: Let's Encrypt cert at `/etc/letsencrypt/live/oxycode.duckdns.org/` (expires Nov 21 2026)
- **Nginx**: Reverse proxy port 443 → 8000 with SSL

### 5. Cloudflare Pages
- **Project Name**: `oxycode-miniapp`
- **Production URL**: https://oxycode-miniapp.pages.dev
- **Wrangler Config**: `~/.wrangler/config/default.toml` on VPS

### 6. Telegram Bot
- **Bot Token**: `$BOT_TOKEN`
- **Admin IDs**: `$ADMIN_IDS`
- **MINI_APP_URL**: `https://oxycode-miniapp.pages.dev`

### 7. OpenCode API Key
```
$OPENCODE_API_KEY
```

### 8. JWT Secret
```
$JWT_SECRET
```

---

## Local Development

### Setup
```bash
# Clone repo
git clone https://github.com/teleforgeofficiall/oxycode-ai.git
cd oxycode-ai

# Install dependencies
bun install  # or npm install

# Create .dev.vars (copy from .dev.vars.example)
cp .dev.vars.example .dev.vars
# Edit .dev.vars with your env vars

# Start dev server
bun run dev
# Opens at http://localhost:5173
```

### Local Commands
```bash
bun run dev          # Start dev server
bun run build        # Build for production
bun run typecheck    # Check TypeScript errors
bun run lint         # Run ESLint
bun run test         # Run tests
```

---

## Git Workflow

### Push to GitHub
```bash
git add .
git commit -m "your message"
git push origin main
```

### Important Notes
- **Local DNS is poisoned** (Wi-Fi DNS hijacked to `127.0.2.2`/`127.0.2.3`)
- **Cannot push to GitHub from local machine**
- **Cannot deploy to Cloudflare Pages from local machine**
- **Must use VPS for all deployments**

---

## VPS Deployment Steps

### Method: Upload dist via Python paramiko

#### Step 1: Build locally
```bash
bun run build
```

#### Step 2: Create deploy zip (dist + functions)
```python
# Script: scripts/deploy-full.py
# Creates deploy-full.zip with:
#   - dist/* (static frontend files)
#   - functions/* (Cloudflare Pages proxy functions)
```

#### Step 3: Upload to VPS and deploy
```python
# Script: scripts/deploy-full.py
# 1. Connects to VPS via SSH (paramiko)
# 2. Uploads deploy-full.zip to /tmp/
# 3. Extracts to /tmp/deploy-full/
# 4. Runs: cd /tmp/deploy-full && npx wrangler pages deploy . --project-name=oxycode-miniapp --branch=main
# 5. Cleans up temp files
```

#### Or run manually:
```bash
# From local machine
python scripts/deploy-full.py
```

### What Gets Deployed
| File | Purpose |
|------|---------|
| `dist/*` | Static React app (HTML, JS, CSS, assets) |
| `functions/[[catchall]].js` | Cloudflare Pages function that proxies `/api/*` to VPS backend |

---

## Backend Deployment (VPS)

### Restart Services
```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Restart bot
systemctl restart oxycode-bot.service

# Restart API
systemctl restart oxycode-api.service

# Check status
systemctl status oxycode-bot.service
systemctl status oxycode-api.service

# View logs
journalctl -u oxycode-bot.service -f
journalctl -u oxycode-api.service -f
```

### Update Backend Code
```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Edit files
nano /root/oxycode-bot/api_server.py
nano /root/oxycode-bot/main.py

# Or upload via paramiko from local machine
python scripts/upload-to-vps.py
```

---

## Database Migrations

### Run via Neon (from VPS)
```python
# Script: scripts/run-migration.py
# Uses psycopg2 to connect to Neon and run SQL

# Example migration:
ALTER TABLE chats ADD COLUMN IF NOT EXISTS agent_type TEXT DEFAULT 'oxygent';
```

### Or via local Python (if psycopg2 available)
```python
import psycopg2

DB_URL = "postgresql://neondb_owner:YOUR_NEON_PASSWORD@ep-green-glitter-afigkd43-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS agent_type TEXT DEFAULT 'oxygent';")
conn.commit()
```

---

## Environment Variables

### Frontend (.dev.vars / Vite env)
```
VITE_API_URL=https://oxycode.duckdns.org
VITE_WS_URL=wss://oxycode.duckdns.org
```

### Backend (.env on VPS at /root/oxycode-bot/.env)
```
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
DATABASE_URL=$DATABASE_URL
JWT_SECRET=$JWT_SECRET
MAINTENANCE_MODE=false
CLOUDFLARE_CLIENT_ID=
CLOUDFLARE_CLIENT_SECRET=
CLOUDFLARE_REDIRECT_URI=https://YOUR_VPS_IP:8000/cloudflare-callback
WEBSOCKET_BASE_URL=wss://oxycode.duckdns.org
OPENCODE_API_KEY=$OPENCODE_API_KEY
```

---

## Quick Deploy Checklist

- [ ] `bun run build` (builds frontend)
- [ ] `python scripts/deploy-full.py` (uploads to VPS, deploys to CF Pages)
- [ ] Verify: `https://oxycode-miniapp.pages.dev` returns HTTP 200
- [ ] Verify: `/api/auth/csrf-token` returns JSON token
- [ ] Backend services running: `systemctl status oxycode-bot.service oxycode-api.service`
- [ ] DB migration applied (if schema changed)

---

## Troubleshooting

### "Failed to obtain CSRF token"
- **Cause**: CF Pages function not deployed (only static files uploaded)
- **Fix**: Deploy with `functions/` directory included (use `scripts/deploy-full.py`)

### "This app works inside Telegram"
- **Cause**: App opened in browser instead of Telegram Mini App
- **Fix**: Open via Telegram bot: https://t.me/OXYCODE_AI_BOT?startapp

### "Backend unavailable" (502)
- **Cause**: VPS backend is down
- **Fix**: `ssh root@YOUR_VPS_IP && systemctl restart oxycode-api.service`

### Cannot push to GitHub from local
- **Cause**: Local DNS poisoned
- **Fix**: Use VPS to push, or fix DNS

### Cannot deploy from local via wrangler
- **Cause**: Local DNS poisoned
- **Fix**: Use VPS deployment script (`scripts/deploy-full.py`)
