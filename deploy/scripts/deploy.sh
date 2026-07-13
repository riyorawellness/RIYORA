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
[ -f .env ] || die "Missing .env — copy .env.example and fill it in"
[ -f ../backend/firebase-admin.json ] || die "Missing backend/firebase-admin.json (upload from Firebase Console → Project Settings → Service Accounts)"
[ -f ../backend/requirements.txt ] || die "backend/requirements.txt missing — is this the repo root?"
ok "docker + env + firebase JSON found"

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
