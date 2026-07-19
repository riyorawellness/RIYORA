#!/usr/bin/env bash
# =============================================================================
# certbot-init.sh — first-time Let's Encrypt bootstrap
# Called by deploy.sh only when no cert exists yet for $DOMAIN.
# =============================================================================
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

echo "▶ Requesting Let's Encrypt cert for $DOMAIN${API_DOMAIN:+ + $API_DOMAIN}"
mkdir -p certbot/conf certbot/www nginx

# ---- Defensive cleanup: previous runs may have left le-bootstrap.conf as an
#      empty DIRECTORY (Docker's default when a host bind-mount source is
#      missing). Remove it so the heredoc below can create a proper file.
if [ -d nginx/le-bootstrap.conf ]; then
  echo "▶ Removing stale directory nginx/le-bootstrap.conf/"
  rm -rf nginx/le-bootstrap.conf
fi

# ---- Write bootstrap nginx config BEFORE any docker mount references it.
cat > nginx/le-bootstrap.conf <<'EOF'
server {
  listen 80 default_server;
  server_name _;
  location /.well-known/acme-challenge/ { root /var/www/certbot; }
  location / { return 200 "certbot bootstrap ok"; add_header Content-Type text/plain; }
}
EOF

# Sanity-check we actually made a file (not a directory).
[ -f nginx/le-bootstrap.conf ] || { echo "✗ Failed to write nginx/le-bootstrap.conf"; exit 1; }

# ---- Free port 80 in case another container / nginx is already bound.
docker rm -f le-bootstrap 2>/dev/null || true
if docker ps --format '{{.Names}}' | grep -q '^riyora-nginx$'; then
  echo "▶ Stopping riyora-nginx temporarily so port 80 is free for cert issuance"
  docker stop riyora-nginx >/dev/null 2>&1 || true
  NGINX_WAS_UP=1
fi

# ---- Start a minimal nginx that only serves the ACME challenge on port 80.
docker run --rm -d --name le-bootstrap \
  -p 80:80 \
  -v "$PWD/certbot/www:/var/www/certbot:ro" \
  -v "$PWD/nginx/le-bootstrap.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:1.27-alpine >/dev/null

# Give nginx a couple of seconds to be actually listening.
sleep 3

# ---- Ask certbot for the certificate.
# If API_DOMAIN is set (recommended for Razorpay webhooks on api.<base>),
# include it as an additional SAN so ONE certificate covers both hostnames.
CERTBOT_DOMAIN_FLAGS=(-d "$DOMAIN")
if [ -n "${API_DOMAIN:-}" ] && [ "${API_DOMAIN}" != "${DOMAIN}" ]; then
  CERTBOT_DOMAIN_FLAGS+=(-d "$API_DOMAIN")
fi

docker run --rm \
  -v "$PWD/certbot/conf:/etc/letsencrypt" \
  -v "$PWD/certbot/www:/var/www/certbot" \
  certbot/certbot:latest \
  certonly --webroot -w /var/www/certbot \
    --email "$LETSENCRYPT_EMAIL" \
    --agree-tos --no-eff-email \
    --non-interactive \
    --expand \
    "${CERTBOT_DOMAIN_FLAGS[@]}"

# ---- Tear down the bootstrap; deploy.sh will bring up the real nginx next.
docker stop le-bootstrap 2>/dev/null || true

# Restart the real nginx if we had stopped it.
if [ "${NGINX_WAS_UP:-0}" = "1" ]; then
  docker start riyora-nginx >/dev/null 2>&1 || true
fi

echo "✔ Certificate issued for $DOMAIN${API_DOMAIN:+ + $API_DOMAIN}"
