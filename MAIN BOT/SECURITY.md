# OXYCODE AI Mini App — Security Checklist

## Authentication & Authorization

- [x] Telegram Mini App `initData` verified via HMAC-SHA256
- [x] JWT tokens expire after 7 days
- [x] JWT secret stored in environment variable
- [x] All API endpoints require valid JWT (except `/api/auth/telegram` and health check)
- [x] User can only access their own projects (user_id check in queries)

## Input Validation

- [x] Telegram initData validated (hash check, auth_date within 10 min)
- [x] Project names sanitized for Cloudflare (lowercase, alphanumeric + hyphens)
- [x] SQL queries use parameterized statements (psycopg2 %s)
- [x] No raw SQL string interpolation
- [x] File upload size limited (aiohttp timeout)

## Secrets & Credentials

- [ ] **TODO**: Move `JWT_SECRET` to `.env` file (not hardcoded)
- [ ] **TODO**: Move `CLOUDFLARE_CLIENT_SECRET` to `.env`
- [ ] **TODO**: Rotate `JWT_SECRET` before production deployment
- [ ] Cloudflare API tokens stored encrypted in database (consider encrypting at rest)
- [ ] `.env` file added to `.gitignore`

## API Security

- [x] CORS configured (allow all origins for Mini App — tighten in production)
- [x] Rate limiting on AI chat (20 messages/day per user)
- [x] AI model fallback with retry limits (prevents infinite loops)
- [x] Error messages don't leak internal details (generic error responses)

## Database Security

- [x] Database connection uses SSL (Neon Postgres requirement)
- [x] Schema isolation for staging/production (OXYGENT_SCHEMA env var)
- [x] Connection pool with validation
- [x] All user_id columns are BIGINT (Telegram IDs are 64-bit)

## Deployment Security

- [ ] **TODO**: Use HTTPS for VPS API server (not HTTP)
- [ ] **TODO**: Add rate limiting middleware to FastAPI
- [ ] **TODO**: Add request size limits
- [ ] **TODO**: Add logging for security events (failed auth, rate limits)
- [ ] **TODO**: Set up monitoring/alerting for suspicious activity

## Known Issues (Fix Before Launch)

1. **JWT_SECRET hardcoded** — Move to `.env`
2. **No HTTPS** — Add TLS certificate (Let's Encrypt)
3. **No rate limiting** — Add slowapi or similar
4. **Cloudflare tokens unencrypted** — Consider encrypting at rest
5. **CORS allows all origins** — Tighten to specific domains

## Environment Variables Required

```env
# Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321

# Database
DATABASE_URL=postgresql://user:pass@host/dbname

# JWT
JWT_SECRET=your-random-secret-here

# Cloudflare OAuth
CLOUDFLARE_CLIENT_ID=your_client_id
CLOUDFLARE_CLIENT_SECRET=your_client_secret
CLOUDFLARE_REDIRECT_URI=https://your-domain.com/cloudflare-callback

# AI
OPENCODE_ZEN_MODEL=mimo-v2.5-free
OPENCODE_ZEN_FALLBACKS=deepseek-v4-flash-free,hy3-free
```

## Pre-Launch Checklist

1. [ ] Set all environment variables on VPS
2. [ ] Generate strong JWT_SECRET (min 32 chars)
3. [ ] Create Cloudflare OAuth App
4. [ ] Set up HTTPS (nginx + Let's Encrypt)
5. [ ] Run database migrations
6. [ ] Test auth flow end-to-end
7. [ ] Test Cloudflare connection flow
8. [ ] Test deployment flow
9. [ ] Test error/fix system
10. [ ] Set up monitoring and alerts
