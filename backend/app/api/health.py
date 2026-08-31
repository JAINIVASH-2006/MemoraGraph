"""
MemoraGraph API – Health Check

Provides system health, liveness, and service connectivity status.
"""

from fastapi import APIRouter
from datetime import datetime, timezone
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

# Track application start time
_start_time = datetime.now(timezone.utc)


@router.get("/healthz")
@router.get("/api/healthz")
async def liveness_check():
    """
    Fast liveness probe for container orchestrators and Render.
    Returns immediately without blocking on external database calls.
    """
    return {"status": "ok"}


@router.get("/api/health")
async def health_check():
    """
    Returns system health status, version, and uptime.
    Performs concurrent connectivity checks for PostgreSQL, Neo4j, and Qdrant
    with strict timeouts to ensure response time is under 1.5 seconds.
    """
    from app.config import settings
    from app.models.database import ping_db
    from app.graph.neo4j_client import get_neo4j
    from app.embeddings.vector_store import get_vector_store

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _start_time).total_seconds()

    async def check_postgres() -> bool:
        try:
            return await asyncio.wait_for(ping_db(), timeout=1.5)
        except Exception as e:
            logger.debug("PostgreSQL health check timeout/error: %s", e)
            return False

    async def check_neo4j() -> bool:
        try:
            neo4j_client = get_neo4j()
            return await asyncio.wait_for(neo4j_client.ping(), timeout=1.5)
        except Exception as e:
            logger.debug("Neo4j health check timeout/error: %s", e)
            return False

    async def check_qdrant() -> bool:
        try:
            qdrant_client = get_vector_store()
            return await asyncio.wait_for(qdrant_client.ping(), timeout=1.5)
        except Exception as e:
            logger.debug("Qdrant health check timeout/error: %s", e)
            return False

    # Run all database pings concurrently
    postgres_ok, neo4j_ok, qdrant_ok = await asyncio.gather(
        check_postgres(),
        check_neo4j(),
        check_qdrant(),
        return_exceptions=True,
    )

    postgres_ok = postgres_ok is True
    neo4j_ok = neo4j_ok is True
    qdrant_ok = qdrant_ok is True

    services_status = {
        "backend": "up",
        "postgres": "up" if postgres_ok else "down",
        "neo4j": "up" if neo4j_ok else "down",
        "qdrant": "up" if qdrant_ok else "down",
    }

    overall = "healthy"
    if not postgres_ok or not neo4j_ok or not qdrant_ok:
        overall = "degraded"

    return {
        "status": overall,
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": now.isoformat(),
        "uptime_seconds": round(uptime_seconds, 1),
        "services": {
            k: {"status": v} for k, v in services_status.items()
        },
    }

