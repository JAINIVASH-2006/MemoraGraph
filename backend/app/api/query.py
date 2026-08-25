"""
MemoraGraph API – Question Answering & Query History Endpoints

POST /api/query                  – Process natural language query
GET  /api/query/history          – View past queries and answers
POST /api/query/feedback/{id}    – Submit helpful/unhelpful rating
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_session
from app.models.query import Query, QuerySource, Feedback, AuditLog
from app.models.user import User
from app.security.auth import get_current_user, get_current_user_optional
from app.schemas.query import QueryRequest, QueryResponse, QueryHistoryItem
from app.llm.generator import get_answer_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def ask_question(
    body: QueryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    """
    Submit a natural language question.
    Runs the intent-routed hybrid Graph RAG pipeline and stores query/history.
    """
    logger.info("Received query: '%s'", body.query)
    generator = get_answer_generator()
    
    # Run the full pipeline with user isolation
    from app.models.user import UserRole
    target_user_id = current_user.id if current_user and current_user.role != UserRole.ADMIN else None
    response = await generator.generate_answer(body.query, top_k=body.top_k, user_id=target_user_id)

    user_id = current_user.id if current_user else None

    # Save to PostgreSQL query history
    db_query = Query(
        id=response.query_id,
        user_id=user_id,
        query_text=body.query,
        answer=response.answer,
        intent=response.intent,
        intent_confidence=response.intent_confidence,
        fallback_used=response.retrieval_metadata.fallback_used,
        retrieval_time_ms=response.retrieval_metadata.retrieval_time_ms,
        generation_time_ms=response.retrieval_metadata.generation_time_ms,
        total_time_ms=response.retrieval_metadata.total_time_ms,
        llm_model=response.retrieval_metadata.llm_model,
        vector_chunks_retrieved=response.retrieval_metadata.vector_chunks_retrieved,
        graph_nodes_retrieved=response.retrieval_metadata.graph_nodes_retrieved,
        graph_edges_traversed=response.retrieval_metadata.graph_edges_traversed,
        answer_confidence=response.confidence,
    )
    session.add(db_query)

    # Save source citations to PostgreSQL
    for s in response.sources:
        db_source = QuerySource(
            query_id=response.query_id,
            document_id=s.document_id,
            document_name=s.document_name,
            chunk_id=s.chunk_id,
            chunk_text=s.text,
            relevance_score=s.score,
            source_type=s.source_type,
        )
        session.add(db_source)

    # Audit log
    audit = AuditLog(
        user_id=user_id,
        action="QUERY_SUBMITTED",
        resource_type="query",
        resource_id=response.query_id,
        details={
            "intent": response.intent,
            "confidence": response.confidence,
            "fallback_used": response.retrieval_metadata.fallback_used,
        }
    )
    session.add(audit)
    
    await session.commit()
    return response


@router.get("/history", response_model=list[QueryHistoryItem])
async def get_query_history(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[QueryHistoryItem]:
    """Retrieve history of past queries for the logged-in user."""
    from app.models.user import UserRole
    stmt = select(Query)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Query.user_id == current_user.id)
    
    stmt = stmt.order_by(desc(Query.created_at)).offset(offset).limit(limit)
    result = await session.execute(stmt)
    queries = result.scalars().all()
    return [QueryHistoryItem.model_validate(q) for q in queries]


@router.post("/feedback/{query_id}", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    query_id: str,
    helpful: bool,
    comment: Optional[str] = None,
    rating: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Submit rating or comments on an AI answer."""
    # Check if query exists
    result = await session.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found.")

    # Check if feedback already exists for this query
    result = await session.execute(select(Feedback).where(Feedback.query_id == query_id))
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.helpful = helpful
        existing.comment = comment or existing.comment
        existing.rating = rating or existing.rating
    else:
        db_fb = Feedback(
            query_id=query_id,
            user_id=current_user.id,
            helpful=helpful,
            comment=comment,
            rating=rating,
        )
        session.add(db_fb)

    # Log action
    audit = AuditLog(
        user_id=current_user.id,
        action="FEEDBACK_SUBMITTED",
        resource_type="query",
        resource_id=query_id,
        details={"helpful": helpful, "rating": rating}
    )
    session.add(audit)

    await session.commit()
    return {"status": "success", "message": "Feedback submitted successfully."}
