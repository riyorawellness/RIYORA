#!/usr/bin/env bash
# =============================================================================
# rollback.sh — flip both backend + frontend back to their previous image tags
# =============================================================================
# Auto-called by deploy.sh when verify.sh fails; can also be run manually.
#
# Usage:  ./scripts/rollback.sh
# =============================================================================
set -Eeuo pipefail
cd "$(dirname "$0")/.."

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; NC='\033[0m'
step() { echo -e "\n${YEL}▶ $*${NC}"; }
ok()   { echo -e "${GRN}✔ $*${NC}"; }
die()  { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

[ -f .rollback/previous.env ] || die "No previous image snapshot found (.rollback/previous.env missing)"

step "Reading previous image digests"
# shellcheck disable=SC1091
source .rollback/previous.env
[ -n "${backend:-}" ]  || die "No previous backend image digest"
[ -n "${frontend:-}" ] || die "No previous frontend image digest"

step "Stopping running containers"
docker stop  riyora-backend riyora-frontend 2>/dev/null || true
docker rm -f riyora-backend riyora-frontend 2>/dev/null || true

step "Re-tagging previous images as :latest"
docker tag "$backend"  riyora-deploy-backend:latest  || true
docker tag "$frontend" riyora-deploy-frontend:latest || true

step "Bringing rolled-back stack up"
docker compose up -d backend frontend

step "Waiting for backend health"
for i in {1..20}; do
  if docker inspect --format='{{.State.Health.Status}}' riyora-backend 2>/dev/null | grep -q healthy; then
    ok "backend healthy after ${i}0s"
    break
  fi
  sleep 3
  [ $i -eq 20 ] && die "backend never turned healthy after rollback — manual intervention required"
done

step "Running verify.sh on rolled-back version"
if ./scripts/verify.sh; then
  ok "rollback successful — previous version is live"
else
  die "rollback ALSO failed — this is a genuine outage; check docker logs immediately"
fi
