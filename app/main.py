"""
Banking API - Production-Ready FastAPI Application

Main application entry point with middleware, lifespan events, and router registration.
"""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, List

import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    REDIS_AVAILABLE = False

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.models.base import close_db, init_db
from app.routers import accounts, auth, fido_auth, security, transactions
from app.schemas.common import HealthCheckResponse

# Initialize structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger("INFO"),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Redis client for caching and rate limiting (optional)
redis_client: Any | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    global redis_client
    
    # Startup
    logger.info("Starting Banking API", version=settings.APP_VERSION)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis connection (optional)
    redis_client = None
    if REDIS_AVAILABLE and settings.REDIS_URL:
        try:
            redis_client = redis.from_url(  # type: ignore
                settings.REDIS_URL,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            await redis_client.ping()  # type: ignore
            logger.info("Redis connected")
        except Exception as e:
            logger.warning("Redis connection failed, running without Redis", error=str(e))
            redis_client = None
    else:
        if not settings.REDIS_URL:
            logger.info("Redis URL not provided, running without Redis")
        elif not REDIS_AVAILABLE:
            logger.warning("Redis package not installed, running without Redis")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Banking API")
    
    if redis_client and REDIS_AVAILABLE:
        await redis_client.close()  # type: ignore
        logger.info("Redis connection closed")
    
    await close_db()
    logger.info("Database connections closed")


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Banking API - Production-Ready Financial Backend

A secure, scalable banking API built with FastAPI following hexagonal architecture.

### Features
- **Account Management**: Create and manage bank accounts
- **Transactions**: Secure fund transfers with idempotency
- **Authentication**: JWT-based OAuth2 authentication
- **Security**: Rate limiting, CORS, security headers

### Security
All monetary amounts use `decimal.Decimal` for precision.
Idempotency is enforced via `X-Idempotency-Key` header.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Register exception handlers
register_exception_handlers(app)

# CORS Middleware (strict configuration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key", "X-Trace-ID"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=600,
)

# Security Headers Middleware (commented out - install pyjwt-cognito or similar for production)
# app.add_middleware(SecurityHeadersMiddleware)

# Rate Limiting Middleware
app.add_middleware(
    RateLimitMiddleware,
    redis_client=redis_client,
    requests_per_minute=settings.RATE_LIMIT_REQUESTS,
)

# Idempotency Middleware
app.add_middleware(
    IdempotencyMiddleware,
    redis_client=redis_client,
    ttl_seconds=86400,
)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """Add trace ID to all requests for distributed tracing."""
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    logger.info(
        "Request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
        trace_id=getattr(request.state, "trace_id", None),
    )
    
    return response


# OAuth2 scheme for JWT authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency to get current authenticated user from JWT token.
    
    In production, this would validate the token and extract user info.
    For now, it's a placeholder that returns the token subject.
    """
    from app.core.security import get_current_user_id_from_token
    
    try:
        user_id = get_current_user_id_from_token(token)
        return user_id
    except Exception:
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError(message="Invalid or expired token")


# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(fido_auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["FIDO2 Authentication"])
app.include_router(security.router, prefix=f"{settings.API_PREFIX}", tags=["Security & Telemetry"])
app.include_router(accounts.router, prefix=f"{settings.API_PREFIX}/accounts", tags=["Accounts"])
app.include_router(transactions.router, prefix=f"{settings.API_PREFIX}/transactions", tags=["Transactions"])


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": time.time(),
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
    )
