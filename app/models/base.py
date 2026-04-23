"""
SQLAlchemy 2.0 async base model configuration.
"""

import ssl
from typing import Any

from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, registry

from app.core.config import get_settings

settings = get_settings()


# SSL context for asyncpg - required for Render and most cloud PostgreSQL providers
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


class AsyncSession(AsyncAttrs):
    """Custom async session with additional utilities."""

    pass


# Create async engine with connection pooling and SSL support
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    connect_args={"ssl": ssl_context},
    **settings.db_engine_options,
)

# Async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


mapper_registry = registry()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    registry = mapper_registry

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Generate table name from class name (snake_case)."""
        return cls.__name__.lower() + "s"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


async def get_db_session() -> AsyncSession:
    """
    Dependency for getting async database session.
    Properly handles session lifecycle with rollback on error.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
