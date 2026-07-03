"""Request-ID + structured logging middleware."""
from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("riyora.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = req_id
        # Skip static/health noise
        path = request.url.path
        if not (path.startswith("/api/health") or path.startswith("/docs") or path.startswith("/openapi")):
            log.info(
                json.dumps(
                    {
                        "req_id": req_id,
                        "method": request.method,
                        "path": path,
                        "status": response.status_code,
                        "ms": duration_ms,
                        "ip": request.client.host if request.client else None,
                    }
                )
            )
        return response
