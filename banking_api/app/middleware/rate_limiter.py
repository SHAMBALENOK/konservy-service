"""
Rate limiting middleware using sliding window algorithm.
Limits requests per IP or user within a time window.
"""

import time
from typing import Any

import structlog
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")


class RateLimiter:
    """
    Sliding window rate limiter using Redis.
    
    Tracks request counts in time windows and enforces limits.
    """

    def __init__(self, redis_client: Any, default_limit: int = 100, window_seconds: int = 60):
        self.redis = redis_client
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def is_allowed(
        self,
        identifier: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: Unique identifier (IP, user ID, API key)
            limit: Max requests per window (uses default if None)
            window: Time window in seconds (uses default if None)
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if not self.redis:
            return True, limit or self.default_limit

        limit = limit or self.default_limit
        window = window or self.window_seconds
        
        current_time = int(time.time())
        window_start = current_time - window
        
        key = f"ratelimit:{identifier}"

        try:
            # Remove old entries outside the window
            await self.redis.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            request_count = await self.redis.zcard(key)
            
            if request_count >= limit:
                # Get oldest request to calculate retry time
                oldest = await self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1] + window - current_time) + 1
                else:
                    retry_after = window
                return False, 0
            
            # Add current request
            await self.redis.zadd(key, {f"{current_time}:{time.time()}": current_time})
            await self.redis.expire(key, window + 1)
            
            remaining = limit - request_count - 1
            return True, remaining
            
        except Exception as e:
            logger.error("Redis error in rate limiter", error=str(e))
            # Fail open - allow request if Redis is unavailable
            return True, limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limiting on API requests.
    
    Identifies clients by IP address or authenticated user ID.
    Returns 429 Too Many Requests when limit exceeded.
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Any | None = None,
        requests_per_minute: int = 100,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.limiter = RateLimiter(
            redis_client=redis_client,
            default_limit=requests_per_minute,
            window_seconds=60,
        )
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request with rate limit check."""
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Get client identifier (prefer user ID from auth, fallback to IP)
        client_id = self._get_client_identifier(request)

        # Check rate limit
        is_allowed, remaining = await self.limiter.is_allowed(client_id)

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please slow down.",
                    "trace_id": request.headers.get("X-Trace-ID", ""),
                    "details": {"retry_after": 60},
                },
                headers={"Retry-After": "60"},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.limiter.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

        return response

    def _get_client_identifier(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Check for authenticated user ID
        user_id = request.state.user_id if hasattr(request.state, "user_id") else None
        if user_id:
            return f"user:{user_id}"

        # Fallback to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"


def get_rate_limiter(redis_client: Any | None = None) -> RateLimiter:
    """Factory function to create rate limiter instance."""
    return RateLimiter(redis_client=redis_client)
