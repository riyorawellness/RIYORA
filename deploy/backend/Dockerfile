# =============================================================================
# RIYORA Backend Dockerfile — FastAPI + Firebase Admin SDK
# Build context: /app/backend
# =============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps needed for building Python wheels + running the app.
# `mongodb-database-tools` provides `mongodump` / `mongorestore` used by
# the in-app backup+restore feature (Admin → Backups) and by the "auto
# backup before wipe" flow in the Danger Zone. Without it, backups fail
# with "mongodump: not found" (exit 127).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates gnupg \
      libjpeg-dev zlib1g-dev \
 && ARCH="$(dpkg --print-architecture)" \
 && case "$ARCH" in \
      amd64)  MTOOLS_URL="https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-x86_64-100.10.0.deb" ;; \
      arm64)  MTOOLS_URL="https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-arm64-100.10.0.deb" ;; \
      *) echo "Unsupported arch: $ARCH" && exit 1 ;; \
    esac \
 && curl -fsSL -o /tmp/mongotools.deb "$MTOOLS_URL" \
 && apt-get install -y --no-install-recommends /tmp/mongotools.deb \
 && rm -f /tmp/mongotools.deb \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching).
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && pip install "firebase-admin>=7.5.0" "gunicorn>=22" "uvicorn[standard]>=0.30"

# Copy the actual source code.
COPY . .

# Non-root user for security.
RUN useradd --create-home --uid 1000 riyora \
 && chown -R riyora:riyora /app
USER riyora

# Ensure runtime directories exist and are writable.
RUN mkdir -p /app/uploads /app/invoices /app/backups

EXPOSE 8001

# Gunicorn + uvicorn worker for production. 4 workers keeps memory reasonable
# on a 2 GB VPS; bump on beefier hosts.
CMD ["gunicorn", "server:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8001", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
