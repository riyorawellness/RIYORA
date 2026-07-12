# RIYORA — PRODUCTION SECRETS (Do NOT commit)

These credentials must be pasted into the **production** Hostinger VPS at
`/app/backend/.env` (or the equivalent Docker env-file mount). They are
INTENTIONALLY NOT stored in the dev preview pod because mock modes must
stay on there for automated pytests to pass.

## Values (received 2026-02)

```
# ---------- MSG91 (production OTP) ----------
OTP_DEV_MODE=false
MSG91_AUTH_KEY=REDACTED_MSG91_AUTHKEY
MSG91_TEMPLATE_ID=REDACTED_MSG91_TEMPLATE
MSG91_SENDER_ID=Riyora2025

# ---------- Razorpay (live) ----------
RAZORPAY_MOCK_MODE=false
RAZORPAY_KEY_ID=rzp_live_REDACTED
RAZORPAY_KEY_SECRET=REDACTED_RAZORPAY_SECRET
# Fetch the webhook secret from Razorpay dashboard → Settings → Webhooks
RAZORPAY_WEBHOOK_SECRET=<paste_from_dashboard>
```

## Razorpay Webhook

Configure this URL in Razorpay dashboard → Settings → Webhooks:

  https://api.riyorawellness.com/api/payments/razorpay/webhook

Selected events (recommended): payment.captured, payment.failed, order.paid,
subscription.charged, subscription.cancelled.

After creating the webhook, Razorpay will display the webhook secret ONCE.
Paste it into `RAZORPAY_WEBHOOK_SECRET` on the production server.

## Verification steps after deploy

1. SSH into the Hostinger VPS.
2. `docker compose exec backend curl -s http://localhost:8001/api/health/live`
3. As admin at `/admin/qa` → **Run BRV** → confirm "Launch" category shows 9/9 green.
4. Test one manual OTP registration end-to-end.
5. Test one small Razorpay payment (₹1) end-to-end and confirm the webhook
   fires (visible in `activity_log` collection under `razorpay.webhook.*`).

## Security notes

- These keys grant real financial capabilities. Rotate immediately if leaked.
- Never paste them into a chat, ticket, or commit them to git.
- On any refund / dispute, log in to Razorpay dashboard using the RIYORA
  merchant account — this file does NOT include dashboard credentials.
