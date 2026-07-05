# Frontend container — multi-stage: yarn build → nginx serve
# Build args:
#   REACT_APP_BACKEND_URL — baked into the JS at build time

FROM node:20-alpine AS builder

WORKDIR /app

# Deps first for cache
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 300000

# Source + build
COPY . .

ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# CRA will fail hard on lint warnings by default in CI; disable that.
ENV CI=false
RUN yarn build

# ---- Runtime stage ----
FROM nginx:1.25-alpine

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
