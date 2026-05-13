"""
Idempotency middleware for preventing duplicate requests.
Uses Redis to store request fingerprints and responses.
"""

import hashlib
import json
from typing import Any

import structlog
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure idempotent handling of requests.
    
    Uses Idempotency-Key header to detect and prevent duplicate requests.
    Stores request fingerprints and responses in Redis for a configurable TTL.
    
    Only applies to POST, PUT, PATCH methods with specific paths.
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Any | None = None,
        ttl_seconds: int = 86400,  # 24 hours
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.exclude_paths = exclude_paths or [
            "/api/v1/auth",
            "/health",
            "/docs",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request with idempotency check."""
        # Skip if not a mutating method
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key = request.headers.get("X-Idempotency-Key")

        if not idempotency_key:
            return await call_next(request)

        # Generate fingerprint from key + request body
        request_body = await self._get_request_body(request)
        fingerprint = self._generate_fingerprint(idempotency_key, request_body)

        # Check if we have a cached response
        if self.redis:
            try:
                cached_response = await self.redis.get(f"fidi:{fingerprint}")
                if cached_response:
                    logger.info(
                        "Idempotent request detected, returning cached response",
                        fingerprint=fingerprint,
                        path=request.url.path,
                    )
                    response_data = json.loads(cached_response)
                    return Response(
                        content=json.dumps(response_data["body"]),
                        status_code=response_data["status"],
                        headers=response_data["headers"],
                        media_type="application/json",
                    )
            except Exception as e:
                logger.warning(
                    "Redis error during idempotency check",
                    error=str(e),
                    fingerprint=fingerprint,
                )

        # Process the request
        response = await call_next(request)

        # Cache successful responses (2xx, 4xx but not 5xx)
        if response.status_code < 500 and self.redis:
            try:
                # Collect response body
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk

                # Rebuild response to allow reading
                from starlette.responses import JSONResponse

                response_data = {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": json.loads(response_body.decode()) if response_body else {},
                }

                # Store in Redis with TTL
                await self.redis.setex(
                    f"fidi:{fingerprint}",
                    self.ttl_seconds,
                    json.dumps(response_data),
                )

                # Return original response
                return JSONResponse(
                    content=response_data["body"],
                    status_code=response_data["status"],
                    headers=dict(response.headers),
                )

            except Exception as e:
                logger.warning(
                    "Redis error during response caching",
                    error=str(e),
                    fingerprint=fingerprint,
                )

        return response

    async def _get_request_body(self, request: Request) -> bytes:
        """Read request body without consuming it."""
        body = await request.body()
        return body

    def _generate_fingerprint(
        self,
        idempotency_key: str,
        request_body: bytes,
    ) -> str:
        """Generate unique fingerprint for request."""
        hasher = hashlib.sha256()
        hasher.update(idempotency_key.encode())
        hasher.update(request_body)
        return hasher.hexdigest()


def get_idempotency_key(request: Request) -> str | None:
    """Extract idempotency key from request headers."""
    return request.headers.get("X-Idempotency-Key")


async def validate_idempotency_key(request: Request) -> str:
    """
    Validate that idempotency key is present for mutating operations.
    
    Can be used as a dependency for routes that require idempotency.
    """
    if request.method in ("POST", "PUT", "PATCH"):
        key = request.headers.get("X-Idempotency-Key")
        if not key:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Idempotency-Key header is required for this operation",
            )
        return key
    return ""
