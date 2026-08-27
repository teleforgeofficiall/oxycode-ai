# OXYCODE AI Bot - Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Fix three issues: (1) bot shows "Thinking..." but never replies, (2) daily usage limit shows 20 instead of admin-set 50, (3) improve admin panel UI.

**Architecture:** React/TS frontend (Vercel) → Cloudflare Worker (worker/) handles agent system with WebSocket → VPS Python backend (ps-code/) handles Telegram bot, admin panel, and some API endpoints. The frontend's chat connects to the Cloudflare Worker's agent system, NOT the VPS Python backend.

**Tech Stack:** React 19, TypeScript, Cloudflare Workers (Hono), Python FastAPI, PostgreSQL (Neon DB), partysocket WebSocket, TanStack Query

---

## Root Cause Analysis

### Issue 1: "Thinking..." Never Replies
The frontend's use-chat.ts calls piClient.createAgentSession() which hits POST /api/agent on the Cloudflare Worker. The Worker creates an agent, returns a websocketUrl, and the frontend connects via WebSocket. The worker/services/ directory is **missing from disk** — it contains critical services (ate-limit/, igateway-proxy/, sandbox/, secrets/, code-fixer/, csrf/) that the Worker imports. This means the Worker cannot function.

**However**, the project is deployed on Vercel and the Worker code is bundled at build time. The services/ directory may exist in the deployed version but not in this local checkout. We need to verify this.

### Issue 2: Daily Limit Shows 20 Instead of 50
The VPS backend (ps-code/database.py line 442) initializes the settings table with ('daily_limit', '20') using ON CONFLICT DO NOTHING. The admin changed it to 50 via the Telegram bot admin panel (main.py line 403: db.set_setting("daily_limit", str(new_limit))). The get_daily_limit() function (database.py line 593-598) reads from the database correctly.

The frontend gets limits from GET /api/limits/usage which calls the **Cloudflare Worker's** LimitsController, NOT the VPS backend. The Worker's limits system (worker/services/rate-limit/) is a separate system from the VPS Python backend's daily limit. The Worker uses its own credits/limits system.

**Root cause:** The frontend displays limits from the Cloudflare Worker's rate-limit system, which is independent of the VPS backend's daily_limit setting. The "20" the user sees is likely the Worker's default free tier limit, not the VPS daily_limit.

### Issue 3: Admin Panel UI
The admin panel is the VPS Python Telegram bot (ps-code/main.py). The "admin panel UI" the user refers to is likely the settings/home pages in the frontend React app.

---

## Phase 1: Diagnose and Fix the Missing Services Directory

### Task 1: Verify if worker/services/ exists in deployment

- [ ] **Step 1: Check if worker/services/ was gitignored or is in a separate package**

Run: git ls-files worker/services/ to check if files are tracked
Run: cat .gitignore | Select-String "services" to check if gitignored
Run: Get-ChildItem -Path "node_modules" -Directory -Filter "services" -ErrorAction SilentlyContinue | Select-Object FullName to check if it's a package

- [ ] **Step 2: Check if the Worker builds successfully**

Run: 
pm run build from project root
Expected: If services are missing, build will fail with import errors

- [ ] **Step 3: Check the deployed Worker**

The Worker is deployed separately. Check if wrangler.toml or wrangler.jsonc exists and what it references.

**Files:**
- Check: worker/index.ts (imports from ./services/rate-limit/DORateLimitStore)
- Check: worker/app.ts (imports from ./services/rate-limit/rateLimits)
- Check: wrangler.toml or wrangler.jsonc

---

## Phase 2: Fix Daily Limit Mismatch (Frontend vs Backend)

### Task 2: Align the VPS backend daily limit with the Cloudflare Worker's limits

The frontend shows limits from the Cloudflare Worker (GET /api/limits/usage), which uses a credits-based system. The VPS backend has its own daily_limit setting. These are two separate systems.

**Option A: Make the VPS backend's daily limit the source of truth**
- Modify the Cloudflare Worker's LimitsController to read from the VPS backend
- Or: Modify the frontend to fetch from VPS backend instead

**Option B: Update the Worker's free tier limit to match**
- Find where the Worker's default free tier limit is configured
- Change it from 20 to 50

**Recommended: Option B** — simpler, fewer changes.

- [ ] **Step 1: Find the Worker's free tier limit configuration**

Search for: daily_limit, ree_tier, default_limit, 20 in worker config files

**Files to search:**
- worker/config/
- worker/services/rate-limit/ (if it exists)
- worker/database/

- [ ] **Step 2: Update the limit to 50**

Change the default free tier limit from 20 to 50 in the Worker's configuration.

- [ ] **Step 3: Verify VPS backend daily_limit is also set to 50**

Check: SELECT value FROM settings WHERE key = 'daily_limit'; in the database
If not 50, update via: UPDATE settings SET value = '50' WHERE key = 'daily_limit';

---

## Phase 3: Fix "Thinking..." Hang (WebSocket/Agent Issue)

### Task 3: Verify the Agent System is Functional

- [ ] **Step 1: Check if the Worker is deployed and responding**

Run: curl https://oxycode-worker.YOUR_SUBDOMAIN.workers.dev/api/health or check Vercel deployment

- [ ] **Step 2: Check browser console for WebSocket errors**

The frontend logs WebSocket connection attempts. Check for:
- Connection failures
- Authentication errors (401/403)
- Agent initialization failures

- [ ] **Step 3: Check if the agent creates successfully**

The flow is:
1. Frontend → POST /api/agent → Worker creates agent → returns websocketUrl
2. Frontend → WebSocket connect to websocketUrl → Agent handles messages

If step 1 fails, the agent system is broken.
If step 2 fails, the WebSocket handler is broken.

**Files:**
- worker/api/controllers/agent/controller.ts (lines 58-293: startCodeGeneration)
- worker/api/controllers/agent/controller.ts (lines 303-366: handleWebSocketConnection)

### Task 4: Fix Agent Initialization if Broken

If the agent fails to initialize, the most likely causes are:
1. Missing worker/services/ directory (Worker can't build)
2. Durable Objects not configured
3. AI Gateway/proxy not configured
4. Database not accessible from Worker

- [ ] **Step 1: Check Worker deployment logs**

Check Cloudflare dashboard for Worker errors.

- [ ] **Step 2: Verify Durable Objects are configured**

Check wrangler.toml for Durable Object bindings.

- [ ] **Step 3: Verify AI provider configuration**

The Worker uses Cloudflare AI Gateway or direct API calls. Check if the AI provider is configured.

---

## Phase 4: Improve Admin Panel UI

### Task 5: Improve Frontend Settings/Home Pages

- [ ] **Step 1: Read current settings page**

File: src/routes/settings/index.tsx

- [ ] **Step 2: Read current home page**

File: src/routes/home.tsx

- [ ] **Step 3: Design improvements**

Based on user feedback, improve:
- Layout and spacing
- Visual hierarchy
- Interactive elements
- Status displays

---

## Testing Strategy

- **Unit tests:** Run 
pm run test to verify existing tests pass
- **Integration tests:** Test WebSocket connection flow
- **Manual testing:** 
  1. Open Mini App in Telegram
  2. Send a message → verify AI responds (not stuck on "Thinking...")
  3. Check usage limit display → verify it shows 50 (not 20)
  4. Test admin panel → verify rate limit change works

## Risks & Mitigations

- **Risk**: worker/services/ directory is genuinely missing from the repo
  - Mitigation: Check git history to see if it was deleted, or if it's generated at build time
  
- **Risk**: The Cloudflare Worker and VPS backend have independent limit systems
  - Mitigation: Align both systems to use the same limit value (50)

- **Risk**: The "Thinking..." issue may be a deployment problem, not a code problem
  - Mitigation: Check deployment status and logs before making code changes

## Success Criteria

- [ ] User can send a message and receive an AI response (not stuck on "Thinking...")
- [ ] Daily usage limit shows 50 (matching admin configuration)
- [ ] Admin panel UI is improved and functional
- [ ] All existing tests pass
