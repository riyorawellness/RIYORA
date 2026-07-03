# RIYORA WELLNESS — Security Overview

Phase 9 introduces platform-wide hardening. Summary of controls in place.

## Authentication
- **JWT** access + refresh tokens (HS256). Refresh tokens are stored server-side
  with `jti` and can be revoked. Rotation on every `/auth/refresh`.
- **bcrypt** password hashing (`$2b$…`).
- **OTP** — 6-digit codes, 5-minute TTL, 5 resends/hour/mobile. Dev mode uses
  a fixed code (`123456`) for QA convenience; **must be disabled in prod**.
- **Brute-force lockout** — 5 failed logins per mobile within 15 min → temporary
  429 lockout. Tracked in `login_attempts` collection.

## Authorization
- `get_current_user`, `get_current_admin` deps ensure every mutating endpoint
  requires the correct role.
- Admin write actions are audit-logged (`activity_log`).

## Transport Security
- HTTPS is terminated at the Kubernetes ingress.
- `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` — all set
  by `SecurityHeadersMiddleware`.

## Input Validation
- Every request body validated by Pydantic models.
- Free-text search params sanitised (`utils/sanitize.py`) to strip `$` operators
  and escape regex meta-characters.
- File uploads validated (`utils/file_validator.py`) — extension whitelist,
  size caps (image 5 MB, PDF 25 MB, media 500 MB) and magic-byte matching.

## NoSQL Injection Protection
- The API never accepts raw dicts as MongoDB query values. All user input is
  cast to expected primitive types by Pydantic; free-text goes through
  `clean_search()` before being wrapped in `$regex`.

## CORS
- Origins configured via `CORS_ORIGINS` env var (comma-separated); credentials
  allowed only for whitelisted origins.

## Rate Limiting
- Global limiter (`slowapi`) — 120 req/min per IP by default.

## Payment Security
- Razorpay signature verified server-side (`services/payment.py`).
- Idempotency on `(purchase_id, sponsor_membership_id)` for commissions.
- Duplicate `razorpay_payment_id` blocked via unique sparse index.

## Content Security
- Media served via signed URLs from `/api/content/token` → `/api/content/stream/{token}`
  with `no-store` cache headers and 5-minute token TTL.
- PDF/video watermark payload includes `full_name` + `membership_id`.

## Secrets Management
- All secrets loaded from environment variables. `.env` files are git-ignored.
- `JWT_SECRET`, `MONGO_URL`, `RAZORPAY_KEY_SECRET`, `ADMIN_PASSWORD` never logged.

## Logging & Observability
- Every request tagged with `X-Request-ID`.
- Structured JSON access logs.
- Admin-only `/api/health/deep` returns Mongo ping, collection counts, uptime.

## Backup
- `scripts/backup_mongo.sh` — daily `mongodump --gzip` with 14-day retention +
  weekly snapshots.
