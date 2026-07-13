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
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates \
      libjpeg-dev zlib1g-dev \
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
