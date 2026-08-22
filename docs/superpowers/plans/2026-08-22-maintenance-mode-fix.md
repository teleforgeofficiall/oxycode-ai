# Maintenance Mode Fix — Implementation Plan

**Goal:** Fix maintenance mode so non-admins see a dedicated maintenance page (not an overlay), admins retain full app access during maintenance, and all routes (including /profile) work correctly.

**Architecture:** The backend auth endpoint needs to return `maintenance` and `isAdmin` fields. The frontend needs to replace the overlay with a proper maintenance page component and route non-admins to it while keeping admin routes functional. The `ProtectedRoute` must respect maintenance mode for non-admins.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), Cloudflare Kumo UI, React Router, TanStack Query

---

## Root Cause Analysis

Three bugs combine to break the profile page:

1. **Backend auth endpoint blocks non-admins** (`api_server.py:313`): `if telegram_id not in ADMIN_IDS: raise HTTPException(403)` — non-admins never get a token, so `isAuthenticated` is always false.

2. **Backend auth response missing fields** (`api_server.py:343-351`): Frontend expects `maintenance` and `isAdmin` in the response, but the backend doesn't send them. `result.maintenance` is always `undefined`.

3. **Frontend maintenance overlay blocks all routes** (`App.tsx:19`): When `showMaintenance` is true, `AppLayout` and `Outlet` don't render — so no child route (including `/profile`) can display. The `ProtectedRoute` redirect to `/` fires because `isAuthenticated` is false.

## File Structure

| File | Responsibility |
|------|---------------|
| `MAIN BOT/api_server.py` | Backend auth endpoint — add `maintenance`/`isAdmin` to response, remove admin-only gate |
| `src/App.tsx` | Route rendering — conditionally show maintenance page or normal layout |
| `src/components/maintenance-page.tsx` | **NEW** — Dedicated maintenance page for non-admins |
| `src/routes/protected-route.tsx` | Auth guard — handle maintenance mode redirect |
| `src/routes.tsx` | Route definitions — add maintenance page route |

---

## Phase 1: Backend — Fix Auth Response (2 tasks)

### Task 1: Add `maintenance` and `isAdmin` to auth endpoint response

**Files:**
- Modify: `MAIN BOT/api_server.py:343-351`

- [ ] **Step 1: Update the auth/telegram endpoint return value**

In `MAIN BOT/api_server.py`, find the `auth_telegram` function (line 302). Change the return statement from:

```python
return {
    "token": token,
    "user": {
        "id": telegram_id,
        "username": tg_user.get("username"),
        "firstName": tg_user.get("first_name"),
        "lastName": tg_user.get("last_name"),
    },
}
```

To:

```python
return {
    "token": token,
    "user": {
        "id": telegram_id,
        "username": tg_user.get("username"),
        "firstName": tg_user.get("first_name"),
        "lastName": tg_user.get("last_name"),
    },
    "maintenance": db_is_maintenance_mode(),
    "isAdmin": telegram_id in ADMIN_IDS,
}
```

- [ ] **Step 2: Verify the change compiles**

Run: `cd "MAIN BOT" && python -c "from api_server import app; print('OK')"`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add MAIN BOT/api_server.py
git commit -m "fix: add maintenance and isAdmin fields to auth response"
```

---

### Task 2: Remove admin-only restriction from auth endpoint

**Files:**
- Modify: `MAIN BOT/api_server.py:312-314`

- [ ] **Step 1: Remove the admin-only check**

In `MAIN BOT/api_server.py`, find lines 312-314:

```python
# Admin-only restriction
if telegram_id not in ADMIN_IDS:
    raise HTTPException(403, "Access denied. This bot is in private beta.")
```

Replace with:

```python
# All authenticated Telegram users can access the miniapp
# Maintenance mode controls feature access, not authentication
```

- [ ] **Step 2: Verify the change compiles**

Run: `cd "MAIN BOT" && python -c "from api_server import app; print('OK')"`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add MAIN BOT/api_server.py
git commit -m "fix: remove admin-only restriction from auth endpoint"
```

---

## Phase 2: Frontend — Maintenance Page Component (1 task)

### Task 3: Create dedicated maintenance page component

**Files:**
- Create: `src/components/maintenance-page.tsx`

- [ ] **Step 1: Create the maintenance page component**

Create `src/components/maintenance-page.tsx`:

```tsx
import { useAuth } from '@/contexts/auth-context';

export function MaintenancePage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-bg-1 dark:bg-kumo-base flex flex-col items-center justify-center px-6">
      <div className="text-center space-y-6 max-w-md">
        <div className="text-7xl">🔧</div>
        <h1 className="text-3xl font-bold text-kumo-strong">
          Under Maintenance
        </h1>
        <p className="text-kumo-subtle text-lg leading-relaxed">
          We're currently performing maintenance on the system. Please check back later.
        </p>
        {user && (
          <div className="pt-4 border-t border-kumo-line">
            <p className="text-sm text-kumo-subtle">
              Logged in as <span className="font-medium text-kumo-default">{user.first_name}</span>
            </p>
          </div>
        )}
        <div className="pt-4">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-kumo-elevated text-sm text-kumo-subtle">
            <span className="size-2 rounded-full bg-yellow-500 animate-pulse" />
            Maintenance in progress
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `bun run typecheck`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/components/maintenance-page.tsx
git commit -m "feat: add dedicated maintenance page component"
```

---

## Phase 3: Frontend — Route & Layout Logic (3 tasks)

### Task 4: Modify AppInner to render routes during maintenance

**Files:**
- Modify: `src/App.tsx:12-29`

- [ ] **Step 1: Rewrite AppInner to always render Outlet**

Replace the current `AppInner` in `src/App.tsx`:

```tsx
function AppInner() {
  const { isMaintenance, isAdmin } = useAuth();
  const showMaintenancePage = isMaintenance && !isAdmin;

  return (
    <>
      {showMaintenancePage ? (
        <Outlet />
      ) : (
        <AppLayout>
          <Outlet />
        </AppLayout>
      )}
      <Toaster
        richColors
        position="top-right"
      />
    </>
  );
}
```

**Why this works:**
- When maintenance is OFF (`showMaintenancePage = false`): `AppLayout` renders with `Outlet` — normal behavior.
- When maintenance is ON + admin (`isAdmin = true`): `showMaintenancePage = false` — admin gets normal layout.
- When maintenance is ON + non-admin (`isAdmin = false`): `showMaintenancePage = true` — renders `Outlet` directly (no sidebar/header), so the maintenance page route can display.

- [ ] **Step 2: Remove unused import**

Remove the `MaintenanceOverlay` import since we no longer use it:

```tsx
// REMOVE this line:
import { MaintenanceOverlay } from './components/maintenance-overlay';
```

- [ ] **Step 3: Verify no TypeScript errors**

Run: `bun run typecheck`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/App.tsx
git commit -m "fix: always render Outlet so routes work during maintenance"
```

---

### Task 5: Add maintenance page route and update ProtectedRoute

**Files:**
- Modify: `src/routes.tsx`
- Modify: `src/routes/protected-route.tsx`

- [ ] **Step 1: Update ProtectedRoute to handle maintenance mode**

Replace `src/routes/protected-route.tsx`:

```tsx
import { Navigate } from 'react-router';
import { useAuth } from '../contexts/auth-context';
import { Skeleton } from '../components/ui/skeleton';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isMaintenance, isAdmin } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="space-y-4">
          <Skeleton className="h-12 w-48" />
          <Skeleton className="h-4 w-32 mx-auto" />
        </div>
      </div>
    );
  }

  // Non-admin users in maintenance mode should see maintenance page (handled by AppInner routing)
  if (isMaintenance && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 2: Update routes to include maintenance page**

Replace `src/routes.tsx`:

```tsx
import type { RouteObject } from 'react-router';
import { Navigate } from 'react-router';

import App from './App';
import Home from './routes/home';
import Chat from './routes/chat/chat';
import Settings from './routes/settings/index';
import { ProtectedRoute } from './routes/protected-route';
import { MaintenancePage } from './components/maintenance-page';

const routes = [
  {
    path: '/',
    Component: App,
    children: [
      {
        index: true,
        Component: Home,
      },
      {
        path: 'maintenance',
        Component: MaintenancePage,
      },
      {
        path: 'profile',
        element: (
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        ),
      },
      {
        path: 'chat/:chatId',
        element: (
          <ProtectedRoute>
            <Chat />
          </ProtectedRoute>
        ),
      },
      {
        path: 'settings',
        element: <Navigate to="/profile" replace />,
      },
    ],
  },
] satisfies RouteObject[];

export { routes };
```

- [ ] **Step 3: Update Home route to show maintenance page for non-admins**

Replace `src/routes/home.tsx` — add maintenance mode check at the top of the component:

```tsx
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { motion } from 'framer-motion';
import { PaperPlaneTiltIcon } from '@phosphor-icons/react';
import { MaintenancePage } from '@/components/maintenance-page';

const MAX_QUERY_LENGTH = 2000;

export default function Home() {
  const navigate = useNavigate();
  const { user, isAuthenticated, isMaintenance, isAdmin } = useAuth();
  const [query, setQuery] = useState('');

  // Non-admin users see maintenance page on home
  if (isMaintenance && !isAdmin) {
    return <MaintenancePage />;
  }

  const placeholderPhrases = useMemo(
    () => ['a modern portfolio website', 'a Telegram bot', 'a SaaS landing page'],
    [],
  );

  const handleCreateApp = () => {
    if (!query.trim() || query.length > MAX_QUERY_LENGTH) return;

    const encodedQuery = encodeURIComponent(query.trim());
    navigate(`/chat/new?query=${encodedQuery}`);
    setQuery('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCreateApp();
    }
  };

  return (
    <div className="relative flex flex-col items-center w-full min-h-full">
      <title>OXYCODE AI</title>
      <div className="home-atmosphere" aria-hidden>
        <div className="home-atmosphere__spotlight" />
      </div>

      <div className="w-full max-w-3xl px-5 sm:px-6">
        <motion.div
          layout
          transition={{
            layout: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
          }}
          className="flex flex-col items-stretch z-10 w-full mt-[18vh] sm:mt-[22vh] md:mt-[26vh]"
        >
          <div className="mb-6 sm:mb-7 grid gap-2">
            <h1 className="w-full text-center text-[clamp(1.75rem,4.5vw,2.5rem)] font-semibold leading-[1.12] text-kumo-strong/80 z-20">
              What do you want to{' '}
              <span className="font-bold text-[1.1em] tracking-tighter uppercase text-brand-emphasis">
                build
              </span>
              ?
            </h1>
            {user && (
              <p className="text-center text-sm text-kumo-subtle">
                Hey, {user.first_name} 👋
              </p>
            )}
          </div>

          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe what you want to build..."
              rows={3}
              className="w-full rounded-xl border border-kumo-line bg-bg-3/50 px-4 py-3 pr-12 text-sm text-kumo-default placeholder:text-kumo-subtle resize-none focus:outline-none focus:ring-2 focus:ring-brand-emphasis/50"
            />
            <button
              onClick={handleCreateApp}
              disabled={!query.trim()}
              className="absolute right-3 bottom-3 size-9 rounded-lg bg-brand-emphasis text-white flex items-center justify-center disabled:opacity-50 hover:bg-brand-emphasis/90 transition-colors"
            >
              <PaperPlaneTiltIcon weight="duotone" className="size-4" />
            </button>
          </div>

          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-kumo-subtle">
            <span>
              {query.length}/{MAX_QUERY_LENGTH}
            </span>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify no TypeScript errors**

Run: `bun run typecheck`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add src/routes.tsx src/routes/protected-route.tsx src/routes/home.tsx
git commit -m "fix: add maintenance page route and update ProtectedRoute for maintenance mode"
```

---

## Phase 4: Cleanup (1 task)

### Task 6: Remove old MaintenanceOverlay component

**Files:**
- Delete or deprecate: `src/components/maintenance-overlay.tsx`

- [ ] **Step 1: Delete the old overlay component**

```bash
rm src/components/maintenance-overlay.tsx
```

- [ ] **Step 2: Verify no remaining imports**

Run: `grep -r "MaintenanceOverlay" src/`
Expected: No results

- [ ] **Step 3: Verify no TypeScript errors**

Run: `bun run typecheck`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove unused MaintenanceOverlay component"
```

---

## Testing Strategy

- **Manual test — Admin + Maintenance ON:** Login as admin (ID 8972944701 or 7371674958), toggle maintenance ON via Telegram bot `/admin`. Open miniapp → should see normal home page, sidebar, profile page works.
- **Manual test — Non-admin + Maintenance ON:** Login as non-admin user. Open miniapp → should see maintenance page. Navigating to `/profile` should redirect back to maintenance page (via ProtectedRoute).
- **Manual test — Maintenance OFF:** Toggle maintenance OFF. Both admin and non-admin should see normal home page. Profile page works for both.
- **Manual test — Auth flow:** Non-admin can now authenticate (no 403). Auth response includes `maintenance` and `isAdmin` fields.

## Risks & Mitigations

- **Risk:** Backend changes require redeployment to VPS
  - Mitigation: Test locally first, deploy after frontend is ready

- **Risk:** Non-admin users who were previously blocked (403) will now see maintenance page
  - Mitigation: This is the desired behavior — they can authenticate but see maintenance info

- **Risk:** Cached auth tokens in localStorage may not have `isAdmin` field
  - Mitigation: Auth context re-authenticates on new sessions; existing tokens are cleared on logout

## Success Criteria

- [ ] Non-admin users see maintenance page when maintenance is ON
- [ ] Admin users see normal app (sidebar, routes, profile) when maintenance is ON
- [ ] Profile page (`/profile`) works for admin during maintenance
- [ ] Profile page redirects to home for non-admin during maintenance (expected)
- [ ] All routes work normally when maintenance is OFF
- [ ] Non-admin users can authenticate (no 403 error)
- [ ] Auth response includes `maintenance` and `isAdmin` fields
