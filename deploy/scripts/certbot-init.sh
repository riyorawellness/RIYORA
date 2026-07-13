#!/usr/bin/env bash
# =============================================================================
# certbot-init.sh — first-time Let's Encrypt bootstrap
# Called by deploy.sh only when no cert exists yet for $DOMAIN.
# =============================================================================
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

echo "▶ Requesting Let's Encrypt cert for $DOMAIN"
mkdir -p certbot/conf certbot/www

# Start a minimal nginx that only serves the ACME challenge.
docker run --rm -d --name le-bootstrap \
  -p 80:80 \
  -v "$PWD/certbot/www:/var/www/certbot:ro" \
  -v "$PWD/nginx/le-bootstrap.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:1.27-alpine || true

# Ensure the bootstrap config exists.
cat > nginx/le-bootstrap.conf <<'EOF'
server {
  listen 80 default_server;
  server_name _;
  location /.well-known/acme-challenge/ { root /var/www/certbot; }
  location / { return 200 "certbot bootstrap ok"; add_header Content-Type text/plain; }
}
EOF

sleep 3

docker run --rm \
  -v "$PWD/certbot/conf:/etc/letsencrypt" \
  -v "$PWD/certbot/www:/var/www/certbot" \
  certbot/certbot:latest \
  certonly --webroot -w /var/www/certbot \
    --email "$LETSENCRYPT_EMAIL" \
    --agree-tos --no-eff-email \
    -d "$DOMAIN"

docker stop le-bootstrap 2>/dev/null || true
echo "✔ Certificate issued for $DOMAIN"
