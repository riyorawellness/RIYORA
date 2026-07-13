#!/usr/bin/env bash
# =============================================================================
# verify.sh — automated 5-minute post-deploy smoke tests
#
# Two tiers:
#   • CRITICAL  → infra must work.   Any red here → exit 1 → deploy.sh rolls back.
#   • QA-TIER   → app-level checks.  Reds here print a warning but do NOT exit 1.
#     These are typically fixable without redeploying (env value, DB row, etc.)
#     so we do not want to nuke a healthy build for them.
# =============================================================================
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; NC='\033[0m'
CRIT_PASS=0; CRIT_FAIL=0
QA_PASS=0;   QA_FAIL=0

check_critical() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo -e "${GRN}✔${NC} [CRIT] $label"; CRIT_PASS=$((CRIT_PASS+1))
  else
    echo -e "${RED}✗${NC} [CRIT] $label"; CRIT_FAIL=$((CRIT_FAIL+1))
  fi
}

check_qa() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo -e "${GRN}✔${NC} [ QA ] $label"; QA_PASS=$((QA_PASS+1))
  else
    echo -e "${YEL}⚠${NC} [ QA ] $label"; QA_FAIL=$((QA_FAIL+1))
  fi
}

BASE="https://${DOMAIN}"

# ---- CRITICAL: infra / auth / TLS -------------------------------------------
check_critical "backend /api/health returns 200" \
  bash -c "curl -fsS ${BASE}/api/health | grep -q healthy"

check_critical "backend /api/health/live returns 200" \
  bash -c "curl -fsS ${BASE}/api/health/live >/dev/null"

check_critical "frontend homepage returns 200 with <div id=\"root\">" \
  bash -c "curl -fsS ${BASE}/ | grep -q 'root'"

check_critical "Firebase apiKey present in JS bundle" \
  bash -c "curl -fsS ${BASE}/ -L | grep -q AIzaSy || curl -fsS \$(curl -fsS ${BASE}/ | grep -oE '/static/js/main[^\"]+\\.js' | head -1 | sed \"s|^|${BASE}|\") | grep -q AIzaSy"

check_critical "admin login returns access_token" \
  bash -c "curl -fsS -X POST ${BASE}/api/admin/login \
     -H 'Content-Type: application/json' \
     -d '{\"mobile\":\"${ADMIN_MOBILE}\",\"password\":\"${ADMIN_PASSWORD}\"}' | grep -q access_token"

check_critical "OTP endpoints removed" \
  bash -c "curl -sS ${BASE}/api/auth/send-otp -o /dev/null -w '%{http_code}' | grep -q 404"

# ---- QA-TIER: app-level, non-fatal ------------------------------------------
check_qa "firebase/sync endpoint alive" \
  bash -c "curl -sS -X POST ${BASE}/api/auth/firebase/sync \
     -H 'Content-Type: application/json' -d '{\"id_token\":\"xxxxxxxxxxxxxxxxx\"}' \
     -o /dev/null -w '%{http_code}' | grep -q 401"

check_qa "BRV overall PASS" \
  bash -c '
    T=$(curl -fsS -X POST '${BASE}'/api/admin/login \
       -H "Content-Type: application/json" \
       -d "{\"mobile\":\"'"${ADMIN_MOBILE}"'\",\"password\":\"'"${ADMIN_PASSWORD}"'\"}" \
       | python3 -c "import sys,json;print(json.load(sys.stdin)[\"tokens\"][\"access_token\"])")
    curl -fsS '${BASE}'/api/admin/qa/brv -H "Authorization: Bearer $T" \
       | python3 -c "import sys,json;d=json.load(sys.stdin); sys.exit(0 if d[\"overall\"]==\"PASS\" else 1)"
  '

check_qa "Razorpay reports LIVE mode" \
  bash -c '
    T=$(curl -fsS -X POST '${BASE}'/api/admin/login \
       -H "Content-Type: application/json" \
       -d "{\"mobile\":\"'"${ADMIN_MOBILE}"'\",\"password\":\"'"${ADMIN_PASSWORD}"'\"}" \
       | python3 -c "import sys,json;print(json.load(sys.stdin)[\"tokens\"][\"access_token\"])")
    curl -fsS '${BASE}'/api/admin/qa/live-check/status -H "Authorization: Bearer $T" \
       | python3 -c "import sys,json;d=json.load(sys.stdin); sys.exit(0 if d[\"razorpay\"][\"status\"]==\"live\" else 1)"
  '

check_qa "Firebase Admin SDK reports LIVE" \
  bash -c '
    T=$(curl -fsS -X POST '${BASE}'/api/admin/login \
       -H "Content-Type: application/json" \
       -d "{\"mobile\":\"'"${ADMIN_MOBILE}"'\",\"password\":\"'"${ADMIN_PASSWORD}"'\"}" \
       | python3 -c "import sys,json;print(json.load(sys.stdin)[\"tokens\"][\"access_token\"])")
    curl -fsS '${BASE}'/api/admin/qa/live-check/status -H "Authorization: Bearer $T" \
       | python3 -c "import sys,json;d=json.load(sys.stdin); sys.exit(0 if d[\"firebase\"][\"status\"]==\"live\" else 1)"
  '

echo -e "\n─────────────────────────"
echo -e "  Critical: ${GRN}${CRIT_PASS} pass${NC} · ${RED}${CRIT_FAIL} fail${NC}"
echo -e "  QA-tier : ${GRN}${QA_PASS} pass${NC} · ${YEL}${QA_FAIL} warn${NC}"
echo -e "─────────────────────────"

if [ $CRIT_FAIL -gt 0 ]; then
  echo -e "${RED}Critical checks failed — deploy.sh will roll back.${NC}"
  exit 1
fi

if [ $QA_FAIL -gt 0 ]; then
  echo -e "${YEL}QA-tier checks warned (${QA_FAIL}). Deploy is healthy — investigate but no rollback.${NC}"
fi
exit 0
