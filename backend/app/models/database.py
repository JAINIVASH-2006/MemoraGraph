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
    import ssl as ssl_module
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

    global _engine, _async_session_factory

    # Log redacted URL to help debug connection string issues
    try:
        parsed = urlparse(database_url)
        netloc = parsed.netloc
        if "@" in netloc:
            creds, host_port = netloc.split("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                netloc = f"{user}:****@{host_port}"
            else:
                netloc = f"{creds}:****@{host_port}"
        redacted = urlunparse(parsed._replace(netloc=netloc))
        logger.info("Initializing database with URL: %s", redacted)
    except Exception as e:
        logger.warning("Could not log redacted database URL: %s", e)

    # asyncpg does not understand 'sslmode' query param (used by Neon, etc.)
    # Strip it from URL and pass ssl context via connect_args instead.
    connect_args = {}
    if "sslmode=" in database_url:
        parsed = urlparse(database_url)
        query_params = parse_qs(parsed.query)
        query_params.pop("sslmode", None)
        new_query = urlencode(query_params, doseq=True)
        database_url = urlunparse(parsed._replace(query=new_query))
        # Create a proper SSL context for asyncpg
        ssl_ctx = ssl_module.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl_module.CERT_NONE
        connect_args["ssl"] = ssl_ctx

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
