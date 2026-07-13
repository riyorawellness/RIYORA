# =============================================================================
# RIYORA Frontend Dockerfile — React SPA served by nginx
# Build context: /app/frontend
# Multi-stage: node builds the bundle → nginx serves the static files.
# =============================================================================

# ---------- STAGE 1: build ---------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# ARG lines expose docker-compose build args to the environment during `yarn build`.
# Create-React-App bakes REACT_APP_* into the JS bundle at build time; changing them
# later requires a full rebuild (`docker compose build --no-cache frontend`).
ARG REACT_APP_BACKEND_URL
ARG REACT_APP_FIREBASE_API_KEY
ARG REACT_APP_FIREBASE_AUTH_DOMAIN
ARG REACT_APP_FIREBASE_PROJECT_ID
ARG REACT_APP_FIREBASE_STORAGE_BUCKET
ARG REACT_APP_FIREBASE_MESSAGING_SENDER_ID
ARG REACT_APP_FIREBASE_APP_ID

ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL} \
    REACT_APP_FIREBASE_API_KEY=${REACT_APP_FIREBASE_API_KEY} \
    REACT_APP_FIREBASE_AUTH_DOMAIN=${REACT_APP_FIREBASE_AUTH_DOMAIN} \
    REACT_APP_FIREBASE_PROJECT_ID=${REACT_APP_FIREBASE_PROJECT_ID} \
    REACT_APP_FIREBASE_STORAGE_BUCKET=${REACT_APP_FIREBASE_STORAGE_BUCKET} \
    REACT_APP_FIREBASE_MESSAGING_SENDER_ID=${REACT_APP_FIREBASE_MESSAGING_SENDER_ID} \
    REACT_APP_FIREBASE_APP_ID=${REACT_APP_FIREBASE_APP_ID} \
    CI=false \
    GENERATE_SOURCEMAP=false

# Install deps first (layer cache).
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

# Compile production bundle → /app/build
RUN yarn build

# ---------- STAGE 2: runtime -------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA fallback + gzip + long-term asset caching.
COPY --from=build /app/build /usr/share/nginx/html

# nginx-spa.conf is written inline here so this Dockerfile stays self-contained
# and does not depend on files outside the build context (frontend/).
# The canonical source is /app/deploy/frontend/nginx-spa.conf — keep both in sync.
RUN cat > /etc/nginx/conf.d/default.conf <<'NGINX_SPA'
server {
    listen 80 default_server;
    server_name _;

    root   /usr/share/nginx/html;
    index  index.html;

    location ~* \.(?:css|js|woff2?|eot|ttf|otf|svg|ico|png|jpg|jpeg|gif|webp|avif|mp4|webm|mp3)$ {
        expires 30d;
        access_log off;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    location = /service-worker.js {
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
        try_files $uri =404;
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-store" always;
    }

    gzip on;
    gzip_vary on;
    gzip_min_length 512;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
}
NGINX_SPA

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
