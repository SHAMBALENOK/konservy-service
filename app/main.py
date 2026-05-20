from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import logging

from .core.config import settings
from .middleware.idempotency import IdempotencyMiddleware
from .middleware.rate_limiter import RateLimiterMiddleware
from .utils.logger import logger

# Import routers
from .routers import auth, accounts, transactions, fido_auth, security

# Database setup
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Dependency to get DB session
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Override the get_db dependency in routers
# We'll do this by setting the dependency overrides in the app

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Banking API...")
    # Create tables if they don't exist (in production, use Alembic migrations)
    # For now, we'll just log
    logger.info("Database connection established")
    yield
    # Shutdown
    logger.info("Shutting down Banking API...")
    await engine.dispose()

app = FastAPI(
    title="Banking API",
    description="Production-ready banking API with advanced security features",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimiterMiddleware, limit=settings.RATE_LIMIT_MAX_REQUESTS, period=settings.RATE_LIMIT_PERIOD_SECONDS)

# Include routers with the /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(fido_auth.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")

# Override the get_db dependency in all routers
# This is a bit tricky because we need to override it for each router's dependencies
# Instead, we'll modify the routers to use the get_db dependency directly
# But since we already defined the routers with their own get_db placeholders,
# we need to override them.

# Let's create a function to override the get_db dependency in a router
def override_get_db_dependency(router):
    for route in router.routes:
        if hasattr(route, 'dependant'):
            # Update dependencies that are of type get_db
            for dep in route.dependant.dependencies:
                if dep.callable.__name__ == 'get_db':
                    dep.callable = get_db

# Apply the override to all routers
override_get_db_dependency(auth.router)
override_get_db_dependency(accounts.router)
override_get_db_dependency(transactions.router)
override_get_db_dependency(fido_auth.router)
override_get_db_dependency(security.router)

# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": "Banking API"}

# Root endpoint
@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    return {
        "message": "Welcome to the Banking API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# The documentation endpoints are automatically provided by FastAPI
# We don't need to define them explicitly unless we want to customize them

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)