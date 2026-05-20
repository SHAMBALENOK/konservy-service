from fastapi import Request, Response, status
from starlette.middleware.base import BaseMiddleware
import time
from typing import Dict, List

class RateLimiterMiddleware(BaseMiddleware):
    def __init__(self, app, limit: int, period: int):
        super().__init__(app)
        self.limit = limit
        self.period = period
        # In a real application, use a shared store like Redis
        self.request_logs: Dict[str, List[float]] = {}

    async def dispatch(self, request: Request, call_next):
        # Use client IP as identifier (in production, consider using API key or user ID after auth)
        client_ip = request.client.host
        current_time = time.time()

        # Clean up old requests for this IP
        if client_ip in self.request_logs:
            self.request_logs[client_ip] = [t for t in self.request_logs[client_ip] if current_time - t < self.period]
        else:
            self.request_logs[client_ip] = []

        # Check if the request count exceeds the limit
        if len(self.request_logs[client_ip]) >= self.limit:
            return Response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": f"Rate limit exceeded. Try again in {self.period} seconds."},
            )

        # Log the current request
        self.request_logs[client_ip].append(current_time)

        # Proceed to the next middleware or endpoint
        response = await call_next(request)
        return response