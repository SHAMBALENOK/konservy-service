from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Dict, Any

class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.idempotency_store: Dict[str, Dict[str, Any]] = {}

    async def dispatch(self, request: Request, call_next):
        idempotency_key = request.headers.get("X-Idempotency-Key")
        # Only apply to methods that are not safe (POST, PUT, PATCH, DELETE) and have the header
        if request.method in ["POST", "PUT", "PATCH", "DELETE"] and idempotency_key:
            cache_key = f"{request.method}:{request.url.path}:{idempotency_key}"
            # Check if we have a cached response for this key
            if cache_key in self.idempotency_store:
                cached_response = self.idempotency_store[cache_key]
                return Response(
                    content=cached_response["content"],
                    status_code=cached_response["status_code"],
                    headers=cached_response["headers"],
                )
            # If not, we proceed and then cache the response
            response = await call_next(request)
            # Cache the response (only for successful responses: 2xx)
            if 200 <= response.status_code < 300:
                self.idempotency_store[cache_key] = {
                    "content": response.body,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                }
            return response
        else:
            # For safe methods or missing key, just proceed
            return await call_next(request)