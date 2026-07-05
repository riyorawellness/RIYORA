# RIYORA WELLNESS — Backend container
# FastAPI + uvicorn on Python 3.11 slim.

FROM python:3.11-slim

WORKDIR /app

# System deps for wheels that need compilation, plus curl for HEALTHCHECK.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip first (separate RUN so failures don't get masked).
RUN pip install --no-cache-dir --upgrade pip

# Install Python deps. This RUN must fail loudly if pip errors — no `|| true`.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prove uvicorn is actually installed BEFORE building the rest of the image.
# If this fails, the whole build fails — which is what we want.
RUN python -c "import uvicorn, fastapi, motor, pymongo, pydantic; print('deps ok:', uvicorn.__version__, fastapi.__version__)"

# App code.
COPY . .

# Persistent upload dir (volume-mounted in docker-compose.yml).
RUN mkdir -p /app/uploads

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8001/api/health || exit 1

# Module form (`python -m uvicorn`) is PATH-independent.
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
