#!/usr/bin/env bash
# ============================================================================
# RIYORA WELLNESS — MongoDB Restore Script
# ----------------------------------------------------------------------------
# Restore a mongodump archive produced by backup_mongo.sh.
#
# Usage:
#   ./restore_mongo.sh /app/backups/riyora-test_database-20260703-020000.archive.gz
#   ./restore_mongo.sh <archive>  [--drop]   # --drop replaces existing db
# ============================================================================
set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <archive.gz> [--drop]"; exit 1
fi

ARCHIVE="$1"; shift || true
DROP_FLAG=""
if [ "${1:-}" = "--drop" ]; then DROP_FLAG="--drop"; fi

if [ -f "/app/backend/.env" ]; then set -a; . /app/backend/.env; set +a; fi
DB_NAME="${DB_NAME:-test_database}"
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"

echo "[$(date -Iseconds)] Restoring $ARCHIVE -> $DB_NAME  $DROP_FLAG"
mongorestore --uri="$MONGO_URL" \
             --archive="$ARCHIVE" \
             --gzip \
             --nsInclude="${DB_NAME}.*" \
             $DROP_FLAG \
             --quiet

echo "[$(date -Iseconds)] Restore complete."
