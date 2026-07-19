# API subdomain remediation (Razorpay webhook TLS fix)

## Symptom
Razorpay dashboard configured to POST webhooks to
`https://api.riyorawellness.com/api/payments/razorpay/webhook` but
**no events are arriving** at the backend. `Live Check → Webhook coverage`
stays at 0/9.

## Root cause
DNS for `api.riyorawellness.com` resolves to the same VPS as `app.` but
the Let's Encrypt certificate on the VPS was issued **only for
`app.riyorawellness.com`** — the TLS handshake for `api.` fails because
the SAN list doesn't include that hostname. Razorpay's HTTP client
rejects the connection and never delivers.

Verify from anywhere:
```bash
echo | openssl s_client -showcerts \
  -servername api.riyorawellness.com \
  -connect api.riyorawellness.com:443 2>/dev/null \
  | openssl x509 -noout -text \
  | grep -A1 "Subject Alternative Name"
```
If the output only lists `DNS:app.riyorawellness.com`, you have this bug.

---

## Fix — on the VPS (5 min)

1. **Confirm DNS.** `api.riyorawellness.com` must A-record to the same
   server IP as `app.`. If not, add it in your DNS provider now and wait
   for propagation.

2. **Pull the latest deploy scripts** (they already know how to issue a
   SAN cert covering both hostnames):
   ```bash
   cd ~/riyora-wellness/deploy   # or wherever your repo lives
   git pull origin main
   ```

3. **Set the new env var:**
   ```bash
   grep -q "^API_DOMAIN=" .env || echo "API_DOMAIN=api.riyorawellness.com" >> .env
   # Also broaden CORS_ORIGINS to accept the api hostname:
   sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://app.riyorawellness.com,https://api.riyorawellness.com|' .env
   ```

4. **Extend the existing certificate** to cover the new SAN. The updated
   `certbot-init.sh` uses `--expand` so this is safe on an existing cert.
   The updated `deploy.sh` automatically detects a missing SAN and runs it.
   ```bash
   ./scripts/deploy.sh
   ```
   Watch the output for `Certificate issued for app.riyorawellness.com +
   api.riyorawellness.com`.

5. **Verify the new cert** (from any machine with openssl):
   ```bash
   echo | openssl s_client -servername api.riyorawellness.com \
     -connect api.riyorawellness.com:443 2>/dev/null \
     | openssl x509 -noout -text \
     | grep -A1 "Subject Alternative Name"
   # Should now show BOTH DNS:app.riyorawellness.com AND DNS:api.riyorawellness.com
   ```

6. **Smoke-test the webhook path from the public internet:**
   ```bash
   curl -i -X POST https://api.riyorawellness.com/api/payments/razorpay/webhook \
     -H "Content-Type: application/json" -d '{}'
   # Expect HTTP 400 "Invalid webhook signature" — that's the CORRECT
   # response (POST reached the backend but the empty body has no valid
   # HMAC signature). No SSL error means the fix worked.
   ```

7. **Trigger a real event.** Send a Razorpay dashboard test event to the
   webhook, then reload **Admin → Live Check → Webhook coverage**. The
   event you selected should turn green with a `last_seen_at` timestamp.

---

## Manual remediation without running `deploy.sh`

If you'd rather do it by hand (e.g. you want to schedule the deploy for
later), you can extend the cert in place:

```bash
cd ~/riyora-wellness/deploy
# 1. Extend the cert (uses the existing certbot volume).
docker run --rm \
  -v "$PWD/certbot/conf:/etc/letsencrypt" \
  -v "$PWD/certbot/www:/var/www/certbot" \
  certbot/certbot:latest \
  certonly --webroot -w /var/www/certbot \
    --email "$(grep ^LETSENCRYPT_EMAIL .env | cut -d= -f2)" \
    --agree-tos --no-eff-email --non-interactive --expand \
    -d app.riyorawellness.com -d api.riyorawellness.com

# 2. Reload nginx to pick up the new cert.
docker exec riyora-nginx nginx -s reload
```

---

## Rollback

If for any reason you want to remove the `api.` SAN, delete the cert and
re-issue only `-d app.riyorawellness.com`:
```bash
docker run --rm \
  -v "$PWD/certbot/conf:/etc/letsencrypt" \
  certbot/certbot:latest \
  delete --cert-name app.riyorawellness.com --non-interactive
./scripts/deploy.sh   # Will re-issue based on DOMAIN alone (API_DOMAIN empty)
```
