# RIYORA WELLNESS — Hostinger Go-Live Quickstart

End-to-end walkthrough to put your app live on `app.riyorawellness.com` +
`api.riyorawellness.com` with SSL. Follow top-to-bottom. Every command is
copy-paste ready.

Estimated total time: **~2 hours** (mostly waiting on DNS + certbot).

---

## 0. Pre-flight checklist (do these BEFORE touching Hostinger)

- [ ] **Save code to GitHub** — In Emergent chat, click **"Save to GitHub"**.
      Note the repo URL, e.g. `https://github.com/<you>/riyora.git`.
- [ ] **Create MongoDB Atlas free cluster** (steps in §3 below).
- [ ] **Sign up for MSG91** + register your DLT sender ID `RIYORA` and OTP
      template. You'll need `MSG91_AUTH_KEY`, `MSG91_TEMPLATE_ID`,
      `MSG91_SENDER_ID`. See `/app/docs/GOLIVE.md` §2 in this repo.
- [ ] **Buy Hostinger VPS KVM 2** (~$8/month, 2GB RAM). Shared hosting will
      NOT work — FastAPI needs a long-running process.
- [ ] Have your domain `riyorawellness.com` DNS panel handy (Hostinger's
      hPanel → **Domains → DNS/Nameservers**).

---

## 1. Buy + boot the VPS

1. Log in to Hostinger hPanel → **VPS → Order VPS**.
2. Pick **KVM 2** (2 vCPU, 2 GB RAM, 100 GB SSD) — comfortable for a
   few hundred concurrent users. Cheaper KVM 1 works if your budget is
   tight but you'll hit limits sooner.
3. Choose **Ubuntu 22.04 LTS** as the OS template.
4. Set a strong root password when prompted — **save it somewhere safe**.
5. Note the **public IPv4** address Hostinger assigns you (e.g.
   `123.45.67.89`).

---

## 2. Point DNS at the VPS

In Hostinger hPanel → **Domains → riyorawellness.com → DNS/Nameservers**,
add these A-records:

| Type | Name | Points to | TTL |
|------|------|-----------|-----|
| A | `app` | `<your VPS IP>` | 3600 |
| A | `api` | `<your VPS IP>` | 3600 |

Leave the existing `@` (root) and `www` records alone — they still point
to your marketing site. DNS propagation usually takes 5–30 minutes.

Verify from your laptop (once propagation completes):
```bash
dig app.riyorawellness.com +short   # should return your VPS IP
dig api.riyorawellness.com +short   # should return your VPS IP
```

---

## 3. Set up MongoDB Atlas (free tier)

1. Sign up at https://cloud.mongodb.com → **Build a Database → M0 Free**.
2. Region: **Mumbai (ap-south-1)** — closest to Indian users.
3. **Database Access** → Add a database user (`riyora` / strong password).
4. **Network Access** → *Add IP Address* → paste your VPS IP + Confirm.
   (For now `0.0.0.0/0` is acceptable but IP-lock ASAP.)
5. **Connect → Connect your application → Python 3.11** → copy the
   connection string. It looks like:
   ```
   mongodb+srv://riyora:<PASSWORD>@cluster0.abcd.mongodb.net/?retryWrites=true&w=majority
   ```
   Replace `<PASSWORD>` with the real password. Save this — you'll paste
   it into `backend/.env` shortly.

---

## 4. SSH into the VPS and prep it

From your laptop:
```bash
ssh root@<your VPS IP>
```

Once logged in, run these one by one:

```bash
# Update everything
apt update && apt upgrade -y

# Core tools
apt install -y git nginx ufw curl build-essential python3.11 python3.11-venv python3-pip

# Node.js 20 (needed to build the React frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Yarn (project uses yarn, not npm)
npm install -g yarn

# Firewall — only allow SSH + HTTP + HTTPS
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

---

## 5. Clone the code and configure env vars

```bash
mkdir -p /var/www && cd /var/www
git clone https://github.com/<you>/riyora.git
cd riyora
```

### Backend env

```bash
cat > /var/www/riyora/backend/.env <<'EOF'
MONGO_URL="mongodb+srv://riyora:<PASSWORD>@cluster0.abcd.mongodb.net/?retryWrites=true&w=majority"
DB_NAME="riyora_prod"

# Rotate this — must be 64+ random chars. Regenerate with:
# python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET="REPLACE_WITH_FRESH_64_CHAR_SECRET"

JWT_ACCESS_TTL_MIN="15"
JWT_REFRESH_TTL_DAYS="7"

# CORS — comma-separated list of allowed frontend origins
CORS_ORIGINS="https://app.riyorawellness.com,https://riyorawellness.com"

# OTP — set DEV_MODE=false once MSG91 is verified working
OTP_TTL_MIN="5"
OTP_RESEND_LIMIT_PER_HOUR="5"
OTP_DEV_MODE="true"
OTP_DEV_CODE="123456"

# MSG91 — fill these after you complete DLT + template registration
MSG91_AUTH_KEY=""
MSG91_TEMPLATE_ID=""
MSG91_SENDER_ID=""
MSG91_OTP_VAR="OTP"

# Admin seed — CHANGE THIS PASSWORD after first login
ADMIN_MOBILE="9999999999"
ADMIN_PASSWORD="CHANGE_ME_STRONG_PASSWORD"
ADMIN_NAME="RIYORA Admin"

# Company + defaults (do NOT change)
COMPANY_MEMBERSHIP_ID="RW000000"
COMPANY_NAME="RIYORA Wellness"
APP_NAME="riyora-wellness"
FILE_TOKEN_TTL_SEC="300"
DEFAULT_GST_PERCENT="18"
DEFAULT_VALIDITY_DAYS="365"
COMMISSION_L1_PERCENT="10"
COMMISSION_L2_PERCENT="5"
COMMISSION_L3_PERCENT="2"
ACTIVITY_SESSIONS_REQUIRED="4"

# Razorpay — leave in mock mode until you approve AutoPay
RAZORPAY_MOCK_MODE="true"
RAZORPAY_KEY_ID=""
RAZORPAY_KEY_SECRET=""
RAZORPAY_WEBHOOK_SECRET=""

EMERGENT_LLM_KEY=""
EOF
```

Then generate + paste the JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# copy the output → open the file → replace REPLACE_WITH_FRESH_64_CHAR_SECRET
nano /var/www/riyora/backend/.env
```

### Frontend env
```bash
cat > /var/www/riyora/frontend/.env <<'EOF'
REACT_APP_BACKEND_URL=https://api.riyorawellness.com
EOF
```

---

## 6. Install Python deps + start backend as a systemd service

```bash
cd /var/www/riyora/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# emergentintegrations is only needed if you use LLM features
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || true
deactivate
```

Create the systemd unit:
```bash
cat > /etc/systemd/system/riyora-backend.service <<'EOF'
[Unit]
Description=RIYORA Wellness FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/riyora/backend
EnvironmentFile=/var/www/riyora/backend/.env
ExecStart=/var/www/riyora/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now riyora-backend
systemctl status riyora-backend    # should show "active (running)"
```

Quick sanity check:
```bash
curl http://127.0.0.1:8001/api/health
# → {"status":"healthy"}
```

---

## 7. Build the React PWA

```bash
cd /var/www/riyora/frontend
yarn install
yarn build

# Copy the build to nginx's serve path
mkdir -p /var/www/riyora-web
cp -r build/* /var/www/riyora-web/
```

---

## 8. Nginx reverse-proxy config

### Backend site (api.riyorawellness.com)
```bash
cat > /etc/nginx/sites-available/api.riyorawellness.com <<'EOF'
server {
    listen 80;
    server_name api.riyorawellness.com;

    client_max_body_size 25M;   # allow QR / certificate uploads

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
EOF
```

### Frontend site (app.riyorawellness.com)
```bash
cat > /etc/nginx/sites-available/app.riyorawellness.com <<'EOF'
server {
    listen 80;
    server_name app.riyorawellness.com;
    root /var/www/riyora-web;
    index index.html;

    # Long-cache hashed assets
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Service worker MUST NOT be cached
    location = /service-worker.js {
        expires -1;
        add_header Cache-Control "no-store";
    }

    # SPA fallback
    location / {
        try_files $uri /index.html;
    }
}
EOF
```

Enable both sites + reload nginx:
```bash
ln -sf /etc/nginx/sites-available/api.riyorawellness.com /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/app.riyorawellness.com /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Sanity check from your laptop:
```bash
curl http://api.riyorawellness.com/api/health
# → {"status":"healthy"}
```

---

## 9. Enable HTTPS with Let's Encrypt

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d app.riyorawellness.com -d api.riyorawellness.com \
        --agree-tos -m you@yourmail.com --redirect --no-eff-email
```

Certbot rewrites the nginx configs to serve HTTPS with auto-redirect from
HTTP and installs a cron job for auto-renewal. Verify:
```bash
curl -I https://app.riyorawellness.com
curl -I https://api.riyorawellness.com/api/health
```

Test auto-renewal:
```bash
certbot renew --dry-run
```

---

## 10. First-login smoke test

1. Open `https://app.riyorawellness.com/` — landing page should load.
2. Register a real user with your own mobile (dev OTP `123456` since MSG91
   isn't wired yet) — check that referral ID `RW000000` is accepted.
3. Open `https://app.riyorawellness.com/admin/login` → mobile `9999999999`
   → the `ADMIN_PASSWORD` you set in step 5.
4. In admin: **System → Danger zone → Empty app data** → clear the test
   user + all test data before real users arrive.
5. Change the admin password from **Admin users → Reset password** →
   note the new one somewhere safe.

---

## 11. Turn on real SMS OTP

Once your DLT sender ID + template are approved on MSG91:

```bash
nano /var/www/riyora/backend/.env
# Fill in:
#   MSG91_AUTH_KEY="…"
#   MSG91_TEMPLATE_ID="…"
#   MSG91_SENDER_ID="RIYORA"
# And flip:
#   OTP_DEV_MODE="false"

systemctl restart riyora-backend
```

Register with a **different** mobile — you should now receive a real SMS.
Verify that `123456` no longer works.

---

## 12. Push-to-deploy workflow (for future updates)

Every time you make a change in Emergent → click **"Save to GitHub"** →
then on the VPS:

```bash
cd /var/www/riyora
git pull

# If backend changed
cd backend && source venv/bin/activate && pip install -r requirements.txt && deactivate
systemctl restart riyora-backend

# If frontend changed
cd /var/www/riyora/frontend
yarn install
yarn build
rm -rf /var/www/riyora-web/*
cp -r build/* /var/www/riyora-web/
```

Save this as a shell script (`/root/deploy.sh`) once you've done it a
couple of times.

---

## 13. Common problems + fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `502 Bad Gateway` on api. | Backend service not running | `systemctl status riyora-backend`; check `journalctl -u riyora-backend -n 100` |
| Frontend loads but API calls fail with CORS error | `CORS_ORIGINS` doesn't include the frontend URL | Edit `.env`, restart backend |
| Login fails immediately with "invalid mobile" | Admin seed didn't run because `ADMIN_PASSWORD` empty on first boot | Set it in `.env`, restart |
| SMS not delivered even with MSG91 set | DLT template mismatch OR VPS IP not whitelisted on MSG91 | Check MSG91 dashboard → Delivery report |
| Uploads fail after ~10 MB | nginx `client_max_body_size` too small | Already set to 25M in the config above; bump if needed |
| Users see stale UI after deploy | Service worker cache | Force refresh (Ctrl+F5); the SW auto-updates on next visit |
| Atlas connection error `IP not whitelisted` | Forgot to whitelist VPS IP in Atlas | Atlas → Network Access → Add current IP |

---

## 14. What to skip today, add later

- **Postgres migration** — Mongo works. Migrate when you actually need
  ACID transactions across referral tree + payments.
- **Docker/compose** — nice, not required; systemd works.
- **`admin.riyorawellness.com` split** — currently at `/admin/*`. When you
  want the split, it's just a new nginx server block + a hostname check
  in `App.js`.
- **S3 / R2 storage** — uploads land in `/var/www/riyora/backend/uploads`.
  Add a nightly `rclone` sync to R2 for backup; migrate fully when disk
  usage exceeds 20 GB.
- **Daily Atlas backup export** — Atlas Free has automatic snapshots;
  optionally cron a `mongodump` to R2 for extra safety.

---

## 15. Cost summary (per month)

| Service | Cost |
|---|---|
| Hostinger VPS KVM 2 | ~$8 |
| MongoDB Atlas M0 | Free (or ~$9 for M2 dedicated once you outgrow M0) |
| SSL (Let's Encrypt) | Free |
| Domain (already owned) | — |
| MSG91 (SMS OTP) | ~₹0.15/SMS, prepay ~₹500 gets you 3000 OTPs |
| **Total** | **~$8/month** to start |

That's it. You're live. 🎉
