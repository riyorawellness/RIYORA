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
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
