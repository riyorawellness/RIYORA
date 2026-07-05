# RIYORA WELLNESS — Go-live checklist

This is the exact set of steps to flip the app from "dev mode" to a
production account with real Indian mobile OTPs and no test data.

## 1. Empty the test data

1. Log in as admin (`/admin/login`).
2. Go to **Admin → System & security → Danger zone**.
3. Click **Empty app data** and follow the three confirmation dialogs.
   You will have to type `EMPTY APP DATA` (exact, case-sensitive) in step 3.
4. Verify the on-screen "cleared" report shows the number of rows removed.

The admin account, company root (`RW000000`), programs, banners, policies,
and QR/system settings are preserved.

You can also delete individual users from **Admin → Users → 🗑** (soft
delete, mobile freed for re-signup).

## 2. Wire real SMS OTP with MSG91

### One-time MSG91 setup (India DLT)
1. Sign up on https://msg91.com and add balance.
2. Register as a **Principal Entity** on your telecom operator's DLT portal.
3. Register a **6-character sender ID** (e.g. `RIYORA`) — get it approved.
4. Register an **OTP Flow template** whose body is exactly (or matches)
   the DLT-approved wording, with a variable placeholder. Example:
   ```
   Your RIYORA Wellness verification code is ##OTP##. Valid for 5 minutes.
   Do not share it with anyone. — RIYORA
   ```
5. In MSG91 dashboard → **Auth Keys**, create a new key and copy it.
   Whitelist your backend's egress IP(s).
6. From MSG91 dashboard → **SMS → Templates** copy the **Template / Flow ID**.

### Backend env vars

Edit `backend/.env` (or your production secret manager) and set:

```env
MSG91_AUTH_KEY="your-authkey-from-msg91"
MSG91_TEMPLATE_ID="your-flow-or-template-id"
MSG91_SENDER_ID="RIYORA"          # exactly as registered on DLT
MSG91_OTP_VAR="OTP"               # variable name inside the template
OTP_DEV_MODE="false"              # disables the 123456 master OTP
```

Restart the backend (`sudo supervisorctl restart backend`).

The moment all three MSG91 vars are set, the app dispatches real SMS.
When any is missing, we fall back to the dev OTP (`123456`) so local
development still works.

## 3. Verify SMS delivery

1. From the frontend register screen, request an OTP with your own mobile.
2. You should receive an SMS from `RIYORA` within a few seconds.
3. Enter the OTP; registration should complete.
4. Set `OTP_DEV_MODE=false` and confirm that `123456` no longer verifies.

If SMS is not delivered:
- Check MSG91 dashboard → **Reports → Delivery Report** for the exact
  telecom error (usually "template mismatch" or "sender not registered").
- Confirm your IP is whitelisted in MSG91 auth key settings.
- Ensure account balance > 0.

## 4. Password-only login (already active)

- Registration requires an 8+ character password (confirmed by user).
- Login uses mobile + password. OTP is only used for **register** and
  **forgot-password**.
- The admin route `POST /api/admin/users/{id}/reset-password` lets you
  reset any user password; the user's sessions are auto-revoked.

## 5. Everything else that flips for production

- Set `CORS_ORIGINS` to your real frontend URL (comma-separated list).
- Rotate `JWT_SECRET` to a fresh 64+ char value.
- Rotate `ADMIN_PASSWORD` immediately after first login.
- Set `RAZORPAY_MOCK_MODE=false` once Razorpay keys are live (currently
  the manual QR flow handles payments, so this can stay `true`).
- Point `MONGO_URL` at MongoDB Atlas (or your production cluster).
- Configure disk-based uploads (screenshots / certificates) to persistent
  storage or migrate to S3 / R2 before the first live payment.
