"""
MemoraGraph – Query, Feedback, and Audit ORM Models
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # MemoraGraph pipeline metadata
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    intent_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    allowed_relationships: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Performance metrics
    retrieval_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    generation_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # LLM metadata
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Retrieval metadata
    vector_chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    graph_nodes_retrieved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    graph_edges_traversed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answer_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    sources: Mapped[list["QuerySource"]] = relationship(
        "QuerySource", back_populates="query", cascade="all, delete-orphan"
    )
    feedback: Mapped[Optional["Feedback"]] = relationship(
        "Feedback", back_populates="query", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Query id={self.id} intent={self.intent}>"


class QuerySource(Base):
    __tablename__ = "query_sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    document_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chunk_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="vector", nullable=False)

    # Relationships
    query: Mapped["Query"] = relationship("Query", back_populates="sources")

    def __repr__(self) -> str:
        return f"<QuerySource id={self.id} query={self.query_id}>"


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    helpful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    query: Mapped["Query"] = relationship("Query", back_populates="feedback")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
