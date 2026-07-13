#!/usr/bin/env bash
# =============================================================================
# verify.sh — automated 5-minute post-deploy smoke tests
# Exit code 0 = all green. Non-zero = something red → deploy.sh will rollback.
# =============================================================================
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0

check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo -e "${GRN}✔${NC} $label"; PASS=$((PASS+1))
  else
    echo -e "${RED}✗${NC} $label"; FAIL=$((FAIL+1))
  fi
}

BASE="https://${DOMAIN}"

# 1. Backend health (public)
check "backend /api/health returns 200" \
  bash -c "curl -fsS ${BASE}/api/health | grep -q healthy"

# 2. Backend health-live (deeper)
check "backend /api/health/live returns 200" \
  bash -c "curl -fsS ${BASE}/api/health/live >/dev/null"

# 3. Frontend index.html loads
check "frontend homepage returns 200 with <div id=\"root\">" \
  bash -c "curl -fsS ${BASE}/ | grep -q 'root'"

# 4. Firebase Web SDK config is baked in
check "Firebase apiKey present in JS bundle" \
  bash -c "curl -fsS ${BASE}/ -L | grep -q AIzaSy || curl -fsS \$(curl -fsS ${BASE}/ | grep -oE '/static/js/main[^\"]+\\.js' | head -1 | sed \"s|^|${BASE}|\") | grep -q AIzaSy"

# 5. Admin can log in
check "admin login returns access_token" \
  bash -c "curl -fsS -X POST ${BASE}/api/admin/login \
     -H 'Content-Type: application/json' \
     -d '{\"mobile\":\"${ADMIN_MOBILE}\",\"password\":\"${ADMIN_PASSWORD}\"}' | grep -q access_token"

# 6. Firebase Auth on backend reachable (invalid token → 401, not 404)
check "firebase/sync endpoint alive" \
  bash -c "curl -sS -X POST ${BASE}/api/auth/firebase/sync \
     -H 'Content-Type: application/json' -d '{\"id_token\":\"xxxxxxxxxxxxxxxxx\"}' \
     -o /dev/null -w '%{http_code}' | grep -q 401"

# 7. BRV runs green (grabs an admin token first)
check "BRV overall PASS" \
  bash -c '
    T=$(curl -fsS -X POST '${BASE}'/api/admin/login \
       -H "Content-Type: application/json" \
       -d "{\"mobile\":\"'"${ADMIN_MOBILE}"'\",\"password\":\"'"${ADMIN_PASSWORD}"'\"}" \
       | python3 -c "import sys,json;print(json.load(sys.stdin)[\"tokens\"][\"access_token\"])")
    curl -fsS '${BASE}'/api/admin/qa/brv -H "Authorization: Bearer $T" \
       | python3 -c "import sys,json;d=json.load(sys.stdin); sys.exit(0 if d[\"overall\"]==\"PASS\" else 1)"
  '

# 8. Razorpay LIVE key present + non-mock
check "Razorpay reports LIVE mode" \
  bash -c '
    T=$(curl -fsS -X POST '${BASE}'/api/admin/login \
       -H "Content-Type: application/json" \
       -d "{\"mobile\":\"'"${ADMIN_MOBILE}"'\",\"password\":\"'"${ADMIN_PASSWORD}"'\"}" \
       | python3 -c "import sys,json;print(json.load(sys.stdin)[\"tokens\"][\"access_token\"])")
    curl -fsS '${BASE}'/api/admin/qa/live-check/status -H "Authorization: Bearer $T" \
       | python3 -c "import sys,json;d=json.load(sys.stdin); sys.exit(0 if d[\"razorpay\"][\"status\"]==\"live\" else 1)"
  '

# 9. Firebase Admin SDK initialised
check "Firebase Admin SDK reports LIVE" \
  bash -c '
    T=$(curl -fsS -X POST '${BASE}'/api/admin/login \
       -H "Content-Type: application/json" \
       -d "{\"mobile\":\"'"${ADMIN_MOBILE}"'\",\"password\":\"'"${ADMIN_PASSWORD}"'\"}" \
       | python3 -c "import sys,json;print(json.load(sys.stdin)[\"tokens\"][\"access_token\"])")
    curl -fsS '${BASE}'/api/admin/qa/live-check/status -H "Authorization: Bearer $T" \
       | python3 -c "import sys,json;d=json.load(sys.stdin); sys.exit(0 if d[\"firebase\"][\"status\"]==\"live\" else 1)"
  '

# 10. Legacy OTP endpoints must be gone (404)
check "OTP endpoints removed" \
  bash -c "curl -sS ${BASE}/api/auth/send-otp -o /dev/null -w '%{http_code}' | grep -q 404"

echo -e "\n─────────────────────────"
echo -e "  Passed: ${GRN}${PASS}${NC} · Failed: ${RED}${FAIL}${NC}"
echo -e "─────────────────────────"
[ $FAIL -eq 0 ] || exit 1
