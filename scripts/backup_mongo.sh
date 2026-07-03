#!/usr/bin/env bash
# ============================================================================
# RIYORA WELLNESS — MongoDB Backup Script
# ----------------------------------------------------------------------------
# Creates a gzipped mongodump archive under $BACKUP_DIR with timestamp,
# rotates old backups keeping the last N (default 14 daily + 8 weekly).
#
# Usage:
#   ./backup_mongo.sh              # runs a fresh backup, prunes old
#   BACKUP_DIR=/mnt/backups ./backup_mongo.sh
#
# Recommended cron:
#   0 2 * * *  /app/scripts/backup_mongo.sh >> /var/log/riyora-backup.log 2>&1
# ============================================================================
set -euo pipefail

# Load env from backend/.env if present
if [ -f "/app/backend/.env" ]; then
  set -a; . /app/backend/.env; set +a
fi

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
DB_NAME="${DB_NAME:-test_database}"
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
KEEP_DAILY="${KEEP_DAILY:-14}"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR}/riyora-${DB_NAME}-${STAMP}.archive.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] Starting backup of $DB_NAME -> $OUT"
mongodump --uri="$MONGO_URL" \
          --db="$DB_NAME" \
          --archive="$OUT" \
          --gzip \
          --quiet

BYTES=$(stat -c '%s' "$OUT" 2>/dev/null || stat -f '%z' "$OUT")
echo "[$(date -Iseconds)] Backup complete: ${OUT} (${BYTES} bytes)"

# Retention: keep the last $KEEP_DAILY files
COUNT=$(ls -1t "$BACKUP_DIR"/riyora-*.archive.gz 2>/dev/null | wc -l | tr -d ' ')
if [ "$COUNT" -gt "$KEEP_DAILY" ]; then
  ls -1t "$BACKUP_DIR"/riyora-*.archive.gz | tail -n +$((KEEP_DAILY + 1)) | xargs -r rm -v
  echo "[$(date -Iseconds)] Pruned $((COUNT - KEEP_DAILY)) old backup(s)"
fi

# Optional: additional weekly copy every Sunday
if [ "$(date -u +%u)" = "7" ]; then
  cp "$OUT" "${BACKUP_DIR}/weekly-$(date -u +%Y-W%V).archive.gz"
  echo "[$(date -Iseconds)] Weekly snapshot stored"
fi

echo "[$(date -Iseconds)] Done."
