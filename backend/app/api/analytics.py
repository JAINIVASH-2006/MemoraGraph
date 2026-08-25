"""
MemoraGraph API – Analytics & Timeline Endpoints

GET /api/analytics/overview – Total system metrics and distributions
GET /api/timeline           – Chronological event records
"""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_session
from app.models.document import Document
from app.models.query import Query
from app.graph.neo4j_client import get_neo4j
from app.models.user import User
from app.security.auth import get_current_user
from app.schemas.query import TimelineEvent, AnalyticsOverview

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsOverview:
    """Retrieve statistical overview of organizational memory with user isolation."""
    from app.models.user import UserRole
    is_admin = current_user.role == UserRole.ADMIN
    user_id = current_user.id if not is_admin else None

    # 1. Query counts from PostgreSQL
    doc_count_stmt = select(func.count(Document.id))
    if not is_admin:
        doc_count_stmt = doc_count_stmt.where(Document.uploaded_by == current_user.id)
    doc_res = await session.execute(doc_count_stmt)
    total_docs = doc_res.scalar() or 0

    query_count_stmt = select(func.count(Query.id))
    if not is_admin:
        query_count_stmt = query_count_stmt.where(Query.user_id == current_user.id)
    query_res = await session.execute(query_count_stmt)
    total_queries = query_res.scalar() or 0

    avg_time_stmt = select(func.avg(Query.total_time_ms))
    if not is_admin:
        avg_time_stmt = avg_time_stmt.where(Query.user_id == current_user.id)
    avg_res = await session.execute(avg_time_stmt)
    avg_latency = float(avg_res.scalar() or 0.0)

    # 2. Query counts from Neo4j
    neo4j = get_neo4j()
    graph_stats = neo4j.get_stats(user_id=user_id)
    
    total_nodes = graph_stats.get("total_nodes", 0)
    total_rels = graph_stats.get("total_relationships", 0)
    counts = graph_stats.get("node_counts", {})

    total_projects = counts.get("Project", 0)
    total_risks = counts.get("Risk", 0)
    total_decisions = counts.get("Decision", 0)

    return AnalyticsOverview(
        total_documents=total_docs,
        total_entities=total_nodes,
        total_relationships=total_rels,
        total_queries=total_queries,
        total_projects=total_projects,
        total_risks=total_risks,
        total_decisions=total_decisions,
        avg_retrieval_time_ms=round(avg_latency, 2),
    )


@router.get("/timeline", response_model=List[TimelineEvent])
async def get_timeline(
    current_user: User = Depends(get_current_user),
) -> List[TimelineEvent]:
    """
    Retrieve chronological organizational events.
    Queries 'Event' nodes in Neo4j with user scoping.
    """
    neo4j = get_neo4j()
    from app.models.user import UserRole
    is_admin = current_user.role == UserRole.ADMIN

    user_clause = ""
    params = {}
    if not is_admin:
        user_clause = "WHERE (e.user_id = $user_id OR e.user_id IS NULL) "
        params["user_id"] = current_user.id

    cypher = (
        f"MATCH (e:Event) "
        f"{user_clause}"
        f"RETURN e.id as id, e.date as date, e.name as title, e.description as description "
        f"ORDER BY e.date DESC LIMIT 50"
    )
    
    events = []
    try:
        results = neo4j.execute_query(cypher, params)
        for r in results:
            events.append(
                TimelineEvent(
                    id=r["id"],
                    date=r.get("date") or "Unknown Date",
                    title=r.get("title") or "Unnamed Event",
                    description=r.get("description") or "",
                    entity_type="Event",
                    entity_id=r["id"],
                )
            )
    except Exception as e:
        logger.warning("Could not fetch Event nodes from Neo4j: %s", e)

    return events
