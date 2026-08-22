"""
MemoraGraph API – Health Check

Provides system health and service connectivity status.
"""

from fastapi import APIRouter
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])

# Track application start time
_start_time = datetime.now(timezone.utc)


@router.get("/health")
async def health_check():
    """
    Returns system health status, version, and uptime.
    Performs real connectivity checks for PostgreSQL, Neo4j, and Qdrant.
    """
    from app.config import settings
    from app.models.database import ping_db
    from app.graph.neo4j_client import get_neo4j
    from app.embeddings.vector_store import get_vector_store

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _start_time).total_seconds()

    # Check postgres
    postgres_ok = await ping_db()
    
    # Check neo4j
    try:
        neo4j_client = get_neo4j()
        neo4j_ok = await neo4j_client.ping()
    except Exception as e:
        logger.warning("Neo4j health check failed: %s", e)
        neo4j_ok = False

    # Check qdrant
    try:
        qdrant_client = get_vector_store()
        qdrant_ok = await qdrant_client.ping()
    except Exception as e:
        logger.warning("Qdrant health check failed: %s", e)
        qdrant_ok = False

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
