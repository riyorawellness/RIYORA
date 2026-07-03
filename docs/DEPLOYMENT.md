# RIYORA WELLNESS — Deployment Guide

This guide covers deploying RIYORA Wellness to production.

## Architecture

- **Frontend**: React 19 PWA (CRA + Craco) served by nginx / Emergent CDN.
- **Backend**: FastAPI (uvicorn) on port `8001`, managed by supervisord.
- **Database**: MongoDB 6+.
- **Ingress**: Kubernetes ingress rewrites `/api/*` → backend, `/*` → frontend.

## Environment Variables

### Backend (`/app/backend/.env`)
| Key | Required | Purpose |
|---|---|---|
| `MONGO_URL` | ✓ | MongoDB connection string |
| `DB_NAME` | ✓ | Database name |
| `JWT_SECRET` | ✓ | Signing key for JWT — rotate carefully |
| `JWT_ACCESS_TTL_MIN` | | Access token TTL (default 15) |
| `JWT_REFRESH_TTL_DAYS` | | Refresh token TTL (default 7) |
| `OTP_TTL_MIN` | | OTP validity in minutes (default 5) |
| `OTP_DEV_MODE` | | If `true` any OTP = `OTP_DEV_CODE` is accepted (default `123456`) — set `false` in prod |
| `ADMIN_MOBILE` / `ADMIN_PASSWORD` | ✓ | Seed admin credentials |
| `RAZORPAY_MOCK_MODE` | | `true`/`false` — mock payments |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | | Live keys when mock=false |
| `CORS_ORIGINS` | ✓ | Comma-separated allowed origins |

### Frontend (`/app/frontend/.env`)
| Key | Required | Purpose |
|---|---|---|
| `REACT_APP_BACKEND_URL` | ✓ | Public HTTPS base URL |

## Production Checklist

- [ ] Set `OTP_DEV_MODE=false` and integrate a real SMS gateway (Twilio, MSG91, TextLocal).
- [ ] Set `RAZORPAY_MOCK_MODE=false` and populate live keys.
- [ ] Rotate `JWT_SECRET` to a 32-byte random hex string.
- [ ] Configure `CORS_ORIGINS` to the exact prod domain(s).
- [ ] Enable MongoDB backups (`/app/scripts/backup_mongo.sh`) via cron.
- [ ] Verify SSL/HTTPS at the ingress layer.
- [ ] Run **BRV** (`/admin/qa`) — must be `PASS` before go-live.
- [ ] Configure monitoring / alerting on `/api/health/deep`.

## Deploy

The platform (Emergent Kubernetes) hot-reloads on file save. Full redeploy is triggered by
`Save to Github` → CI → Rollout. Manual restart:
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

## Post-Deploy Verification

```bash
curl https://<prod>/api/health/ready
curl https://<prod>/api/health/live
```

The frontend should load with a valid PWA manifest — install prompt appears on
supported browsers after 30s of engagement.
