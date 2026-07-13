# RIYORA — PRODUCTION SECRETS (Do NOT commit)

> ⚠️ **This file must NEVER be committed.** It exists only as a local
> checklist of which environment variables to fill on the VPS.
> The `.gitignore` at repo root excludes `memory/PRODUCTION_ENV.md`.

## What to fill in production `.env`

```
# ---------- Firebase Authentication ----------
FIREBASE_ADMIN_CREDENTIALS_PATH=/app/backend/firebase-admin.json
FIREBASE_PROJECT_ID=<your-firebase-project-id>

# ---------- Razorpay (live) ----------
RAZORPAY_MOCK_MODE=false
RAZORPAY_KEY_ID=<paste_from_razorpay_dashboard>
RAZORPAY_KEY_SECRET=<paste_from_razorpay_dashboard>
RAZORPAY_WEBHOOK_SECRET=<paste_from_dashboard_after_creating_webhook>
```

The real key values are held in a private password manager. Do NOT paste
them into this file or any file inside the repo.

## Where the keys come from

- **Firebase Admin JSON** → Firebase Console → Project Settings → Service
  Accounts → Generate new private key. Upload the JSON to the VPS at
  `/app/backend/firebase-admin.json` via `scp`. **Never commit.**
- **Razorpay key id + secret** → Razorpay Dashboard → Settings → API Keys
  (Live mode).
- **Razorpay webhook secret** → Razorpay Dashboard → Settings → Webhooks →
  create a webhook pointing at `https://<your-domain>/api/payments/razorpay/webhook`
  → copy the secret shown ONCE.

## Verification after deploy

1. SSH into the VPS
2. `docker compose exec backend curl -s http://localhost:8001/api/health` → `{"status":"healthy"}`
3. Log in at `/admin/qa/live-check` → **Razorpay** + **Firebase** both show **LIVE (green)**
4. `/admin/qa` → **Run BRV** → **45/45 PASS**
5. Complete one real ₹1 Razorpay payment end-to-end and confirm the
   webhook event appears in `/admin/qa/live-check` → Recent webhook events

## If a secret ever leaks

1. **Firebase**: Console → Service Accounts → revoke the compromised key
   and generate a new one; upload the fresh JSON to VPS.
2. **Razorpay**: Dashboard → Settings → API Keys → **Regenerate**. Update
   both the VPS `.env` AND any GitHub Actions secrets that reference it.
3. **JWT_SECRET**: Regenerate with `openssl rand -hex 64` and restart the
   backend — this instantly invalidates every existing session.
