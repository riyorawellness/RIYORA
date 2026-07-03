# RIYORA WELLNESS — Backup & Recovery

## Backup
Automated by `/app/scripts/backup_mongo.sh`. Runs `mongodump --gzip` and stores
timestamped archive in `$BACKUP_DIR` (default `/app/backups`).

### Cron
```cron
0 2 * * *  /app/scripts/backup_mongo.sh >> /var/log/riyora-backup.log 2>&1
```
The script keeps the last **14 daily** backups and one **weekly** snapshot every Sunday.

### Manual backup
```bash
BACKUP_DIR=/mnt/nas /app/scripts/backup_mongo.sh
```

## Restore
```bash
# Restore without dropping (merge)
/app/scripts/restore_mongo.sh /app/backups/riyora-test_database-YYYYMMDD-HHMMSS.archive.gz

# Restore replacing existing collections
/app/scripts/restore_mongo.sh <archive> --drop
```

## Media / File Backups
Uploaded files (banners, thumbnails, invoices) live under
`/app/backend/uploads/` and `/app/backend/invoices/`. Include those in the
filesystem-level backup:
```bash
tar czf riyora-files-$(date -u +%Y%m%d).tar.gz \
    /app/backend/uploads /app/backend/invoices
```

## Disaster Recovery
1. Provision a new MongoDB.
2. Update `MONGO_URL` + `DB_NAME` in `/app/backend/.env`.
3. Copy the latest archive + file bundle to the new host.
4. `restore_mongo.sh <archive> --drop`.
5. Untar the file bundle to `/app/backend/`.
6. `sudo supervisorctl restart backend`.
7. Log in as admin → run **BRV** to confirm health.

## Retention Policy Recommendation
- Daily backups: 14 days
- Weekly snapshots: 8 weeks
- Monthly snapshots (manual): 12 months, moved to cold storage
