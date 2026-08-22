"""
MemoraGraph – SQLAlchemy Async Database Engine
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Module-level engine and session factory (initialized in main.py lifespan)
_engine = None
_async_session_factory = None


def init_db(database_url: str) -> None:
    """Initialize the async database engine and session factory."""
    global _engine, _async_session_factory

    # asyncpg does not understand 'sslmode' query param (used by Neon, etc.)
    # Strip it and pass ssl via connect_args instead.
    connect_args = {}
    if "sslmode=" in database_url:
        database_url = database_url.split("?sslmode=")[0] if "?sslmode=" in database_url else database_url.replace("&sslmode=require", "")
        connect_args["ssl"] = "require"

    _engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    logger.info("Database engine initialized.")


async def create_tables() -> None:
    """Create all tables defined in the ORM models."""
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized.")
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_db() -> bool:
    """Test database connectivity."""
    from sqlalchemy import text
    global _engine
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Database ping failed: %s", e)
        return False


async def close_db() -> None:
    """Dispose the engine on shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database engine closed.")
