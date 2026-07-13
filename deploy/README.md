# deploy/ — VPS deployment kit

Turnkey production deployment for RIYORA Wellness.

## Quick start

```bash
# On VPS, one-time:
apt install -y docker-compose-plugin git
git clone <your-repo> /opt/riyora
cd /opt/riyora/deploy
cp .env.example .env
nano .env    # fill in every CHANGE_ME_*
# upload firebase-admin.json to ../backend/firebase-admin.json
./scripts/deploy.sh

# Every subsequent deploy:
cd /opt/riyora/deploy && ./scripts/deploy.sh
```

Full runbook: **[DEPLOYMENT.md](./DEPLOYMENT.md)**

## Files

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | 4 services + certbot |
| `.env.example` | Every env var you must set |
| `backend/Dockerfile` | Python 3.11 + Firebase Admin |
| `frontend/Dockerfile` | Multi-stage node build → nginx serve |
| `frontend/nginx-spa.conf` | SPA fallback inside frontend container |
| `nginx/default.conf` | Outer TLS-terminating reverse proxy |
| `scripts/deploy.sh` | Turnkey deploy + auto-rollback on failed verify |
| `scripts/verify.sh` | 10 post-deploy smoke tests |
| `scripts/rollback.sh` | Flip back to last-good image tags |
| `scripts/certbot-init.sh` | First-time Let's Encrypt bootstrap |

## Never commit

- `.env` (secrets)
- `../backend/firebase-admin.json` (Firebase service account)
- `certbot/` (TLS certs)
- `.rollback/` (image digests)
- `backups/` (Mongo dumps)

The `.gitignore` in this folder handles all of the above.
