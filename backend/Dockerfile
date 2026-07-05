# Backend container — FastAPI + uvicorn
FROM python:3.11-slim

WORKDIR /app

# System deps: build-essential for wheels that need compilation, curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir emergentintegrations \
      --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || true

# App code
COPY . .

# Uploaded media (screenshots, certificates) — mounted as a volume in compose
RUN mkdir -p /app/uploads

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8001/api/health || exit 1

# Use `python -m uvicorn` (module form) instead of the `uvicorn` shell binary.
# Module form is PATH-independent — works regardless of where pip put the
# console-script shim.
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
