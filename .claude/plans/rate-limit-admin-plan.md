# Implementation Plan: Settings?Profile + Admin Rate Limits + Live Preview Gate

## Overview
Three interconnected features for OXYCODE AI Telegram Mini App:
1. Rename Settings to Profile (unified page with Telegram identity, Cloudflare, usage limits)
2. Admin-configurable rolling 24h rate limiting with daily quota toggle
3. Live Preview gated behind Cloudflare connection state

## Requirements
- Replace /settings route with /profile in all 7+ frontend references
- Unified Profile page shows: Telegram identity, Cloudflare connection, usage limits
- Admin panel at /admin for configuring rate limits (rolling window, daily quota, periodSeconds)
- Live Preview disabled when Cloudflare not connected (show disabled state, not redirect)
- No new visual systems—use existing @cloudflare/kumo and @phosphor-icons

## Architecture Changes

### Frontend
- Route: src/routes.tsx ? change /settings to /profile
- Page: src/routes/settings/index.tsx ? rename to src/routes/profile/index.tsx
- Sidebar: src/components/layout/app-sidebar.tsx ? GearIcon?UserIcon, /settings?/profile
- Header: src/components/layout/global-header.tsx ? GearIcon?UserIcon, /settings?/profile
- Auth Context: src/contexts/auth-context.tsx ? expose isAdmin flag
- Limits Context: src/contexts/limits-context.tsx ? expose rolling config
- API Client: src/lib/api-client.ts ? add admin endpoints
- API Types: src/api-types.ts ? add admin types
- Live Preview: src/routes/chat/chat.tsx ? gate preview on Cloudflare connection
- Admin Page: src/routes/admin/index.tsx ? new admin panel

### Backend
- Admin Controller: worker/api/controllers/admin/controller.ts ? new
- Admin Routes: worker/api/routes/adminRoutes.ts ? new
- Route Registration: worker/api/routes/index.ts ? add setupAdminRoutes
- Rate Limit Config: worker/services/rate-limit/config.ts ? add admin config types
- Limits Routes: worker/api/routes/limitsRoutes.ts ? add admin config endpoints
- Auth Middleware: worker/middleware/auth/routeAuth.ts ? add admin role check
- Schema: worker/database/schema.ts ? add admin role field to users table

## Implementation Steps

### Phase 1: Settings?Profile Rename (7 files)
1. Rename route in src/routes.tsx: /settings ? /profile
2. Rename directory src/routes/settings/ ? src/routes/profile/
3. Update sidebar: src/components/layout/app-sidebar.tsx (GearIcon?UserCircle, /settings?/profile)
4. Update header: src/components/layout/global-header.tsx (GearIcon?UserCircle, /settings?/profile)
5. Update usage-limit-checker: src/utils/usage-limit-checker.tsx (/settings?/profile)
6. Update chat route: src/routes/chat/chat.tsx (/settings?/profile at line 1489)
7. Update api-client: src/lib/api-client.ts (if any /settings refs)

### Phase 2: Profile Page Content (1 file)
8. Restructure Profile page (src/routes/profile/index.tsx):
   - Section 1: Telegram Identity (avatar, name, username, ID)
   - Section 2: Cloudflare Connection (connect/disconnect, gateway selection)
   - Section 3: Usage Limits (current usage, reset time, rolling window info)

### Phase 3: Admin Rate Limit Backend (6 files)
9. Add admin role to users table (worker/database/schema.ts)
10. Add admin config storage in KV (worker/config/index.ts)
11. Add admin auth middleware (worker/middleware/auth/routeAuth.ts)
12. Create admin controller (worker/api/controllers/admin/controller.ts)
13. Create admin routes (worker/api/routes/adminRoutes.ts)
14. Register admin routes (worker/api/routes/index.ts)

### Phase 4: Admin Rate Limit Frontend (4 files)
15. Add admin API types (src/api-types.ts)
16. Add admin API methods (src/lib/api-client.ts)
17. Create admin page (src/routes/admin/index.tsx)
18. Add admin route (src/routes.tsx)

### Phase 5: Live Preview Gate (2 files)
19. Gate Live Preview (src/routes/chat/chat.tsx) - check Cloudflare connection
20. Update preview button with disabled state and tooltip

## Testing Strategy
- Unit tests: Admin config storage, rate limit config validation
- Integration tests: Admin CRUD operations, rate limit enforcement
- E2E tests: Profile page navigation, admin panel access, preview gating

## Risks & Mitigations
- Risk: Admin panel security ? Mitigation: Server-side admin role check
- Risk: Rate limit config corruption ? Mitigation: Validate config before saving
- Risk: Live Preview regression ? Mitigation: Test with connected and disconnected states

## Success Criteria
- [ ] /settings redirects to /profile everywhere
- [ ] Profile page shows Telegram identity, Cloudflare, usage limits
- [ ] Admin can configure rate limits via /admin panel
- [ ] Rate limits respect admin config (rolling 24h, daily quota)
- [ ] Live Preview disabled when Cloudflare not connected
- [ ] All existing tests pass
- [ ] New admin endpoints have proper auth checks
