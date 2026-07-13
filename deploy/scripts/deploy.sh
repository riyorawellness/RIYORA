#!/usr/bin/env bash
# =============================================================================
# RIYORA Wellness — turnkey VPS deploy
#   • git pull (or first-time clone if repo not present)
#   • sanity-check required env vars + firebase-admin.json
#   • patch nginx config with the DOMAIN from .env
#   • docker compose build (no-cache for frontend so REACT_APP_* is fresh)
#   • docker compose up -d with graceful rollout
#   • run scripts/verify.sh — aborts + rolls back on any RED
#
# Usage:  cd /opt/riyora && ./scripts/deploy.sh
# =============================================================================
set -Eeuo pipefail

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'
step()  { echo -e "\n${BLU}▶ $*${NC}"; }
ok()    { echo -e "${GRN}✔ $*${NC}"; }
warn()  { echo -e "${YEL}⚠ $*${NC}"; }
die()   { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step "1. Verifying prerequisites"
command -v docker >/dev/null || die "docker not installed"
docker compose version >/dev/null 2>&1 || die "docker compose plugin not installed"

# .env is missing → try to bootstrap from .env.example, else emit a starter.
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    warn "No .env found — copied .env.example → .env. Now open it and fill in every CHANGE_ME_* value:"
    warn "    nano .env"
    exit 1
  else
    warn "Neither .env nor .env.example exists. Writing a starter .env to $(pwd)/.env"
    cat > .env <<'ENVEOF'
# RIYORA production .env — fill in every CHANGE_ME_* value below.
DOMAIN=app.YOURDOMAIN.com
LETSENCRYPT_EMAIL=you@example.com
REACT_APP_BACKEND_URL=https://app.YOURDOMAIN.com
CORS_ORIGINS=https://app.YOURDOMAIN.com

MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=CHANGE_ME_16CHAR_STRONG_MONGO_PASSWORD
DB_NAME=riyora_prod

JWT_SECRET=CHANGE_ME_RUN__openssl_rand_hex_64
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=7

ADMIN_MOBILE=9999999999
ADMIN_PASSWORD=CHANGE_ME_STRONG_ADMIN_PASSWORD

FIREBASE_ADMIN_CREDENTIALS_PATH=/app/firebase-admin.json
FIREBASE_PROJECT_ID=CHANGE_ME_FIREBASE_PROJECT_ID
REACT_APP_FIREBASE_API_KEY=CHANGE_ME_FIREBASE_API_KEY
REACT_APP_FIREBASE_AUTH_DOMAIN=CHANGE_ME.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=CHANGE_ME_FIREBASE_PROJECT_ID
REACT_APP_FIREBASE_STORAGE_BUCKET=CHANGE_ME.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=CHANGE_ME
REACT_APP_FIREBASE_APP_ID=CHANGE_ME

RAZORPAY_MOCK_MODE=false
RAZORPAY_KEY_ID=CHANGE_ME_rzp_live_xxxxxxxx
RAZORPAY_KEY_SECRET=CHANGE_ME_RAZORPAY_SECRET
RAZORPAY_WEBHOOK_SECRET=CHANGE_ME_FROM_RAZORPAY_DASHBOARD

COMPANY_NAME=RIYORA Wellness
SUPPORT_EMAIL=support@example.com
LOG_LEVEL=INFO
ENABLE_HEALTH_CHECK=true
ENVEOF
    warn "Starter .env written. Now open it and fill every CHANGE_ME_* value:"
    warn "    nano .env"
    exit 1
  fi
fi

[ -f ../backend/firebase-admin.json ] || die "Missing backend/firebase-admin.json (upload from Firebase Console → Project Settings → Service Accounts)"
[ -f ../backend/requirements.txt ] || die "backend/requirements.txt missing — is this the repo root?"

# The backend container runs as non-root uid 1000 (see deploy/backend/Dockerfile).
# The bind-mounted firebase-admin.json must be readable by that uid, otherwise
# firebase_admin.credentials.Certificate() throws PermissionError at runtime.
chown 1000:1000 ../backend/firebase-admin.json 2>/dev/null || true
chmod 640       ../backend/firebase-admin.json 2>/dev/null || true

ok "docker + env + firebase JSON found (perms normalised to 1000:1000 640)"

# shellcheck disable=SC1091
set -a; source .env; set +a

# Required env-var sanity
for v in DOMAIN LETSENCRYPT_EMAIL REACT_APP_BACKEND_URL CORS_ORIGINS \
         MONGO_ROOT_PASSWORD JWT_SECRET ADMIN_PASSWORD \
         FIREBASE_PROJECT_ID REACT_APP_FIREBASE_API_KEY \
         RAZORPAY_KEY_ID RAZORPAY_KEY_SECRET RAZORPAY_WEBHOOK_SECRET; do
  # ${!v} is bash indirect expansion.
  if [ -z "${!v:-}" ] || [[ "${!v}" == CHANGE_ME* ]]; then
    die "Env var $v is empty or still set to CHANGE_ME"
  fi
done
ok "All required env vars are set"

step "2. Latest code"
if [ -d .git ]; then
  git pull --ff-only origin main
  ok "git pull ff-only ok"
else
  warn "Not a git repo — skipping pull"
fi

step "3. Injecting DOMAIN into nginx config"
# Substitute app.riyorawellness.com with the real domain from .env.
sed -i "s|app\.riyorawellness\.com|${DOMAIN}|g" nginx/default.conf
ok "nginx/default.conf → ${DOMAIN}"

step "4. Bootstrap TLS certificate (first-time only)"
if [ ! -d certbot/conf/live/"${DOMAIN}" ]; then
  ./scripts/certbot-init.sh
else
  ok "certificate for ${DOMAIN} already exists"
fi

step "5. Snapshot last-good image digests (for rollback)"
mkdir -p .rollback
for svc in backend frontend; do
  img=$(docker inspect --format='{{.Image}}' "riyora-$svc" 2>/dev/null || echo "")
  [ -n "$img" ] && echo "$svc=$img" >> .rollback/current.env || true
done
mv .rollback/current.env .rollback/previous.env 2>/dev/null || true
ok "rollback snapshot saved"

step "6. Building images (no-cache for frontend so Firebase env is baked fresh)"
docker compose build backend
docker compose build --no-cache frontend
ok "images built"

step "7. Rolling update"
docker compose up -d --remove-orphans
ok "containers up"

step "8. Waiting for backend health"
for i in {1..40}; do
  if docker inspect --format='{{.State.Health.Status}}' riyora-backend 2>/dev/null | grep -q healthy; then
    ok "backend healthy after ${i}0s"
    break
  fi
  sleep 3
  [ $i -eq 40 ] && die "backend never turned healthy — check: docker compose logs backend"
done

step "9. Verification (public smoke tests)"
if ./scripts/verify.sh; then
  ok "verification PASSED — deployment complete"
  echo -e "\n${GRN}================================================${NC}"
  echo -e "${GRN}  RIYORA is live at https://${DOMAIN}${NC}"
  echo -e "${GRN}================================================${NC}"
else
  warn "verification FAILED — starting automatic rollback"
  ./scripts/rollback.sh
  die "Deploy failed — rolled back to previous version"
fi
