"""
MemoraGraph – Pydantic Schemas: Query & Retrieval
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    conversation_id: Optional[str] = None


class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class GraphSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    entity_types: Optional[List[str]] = None
    relationship_types: Optional[List[str]] = None
    max_hops: int = Field(default=2, ge=1, le=4)


class Source(BaseModel):
    document_id: str
    document_name: str
    chunk_id: Optional[str] = None
    text: str
    score: float
    source_type: str = "vector"  # "vector" | "graph"


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}


class GraphPath(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    description: Optional[str] = None


class IntentResult(BaseModel):
    intent: str
    confidence: float
    allowed_relationships: List[str]
    fallback_used: bool = False
    low_confidence: bool = False


class RetrievalMetadata(BaseModel):
    vector_chunks_retrieved: int = 0
    graph_nodes_retrieved: int = 0
    graph_edges_traversed: int = 0
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0
    llm_model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    fallback_used: bool = False


class EvidenceObject(BaseModel):
    text: str
    source_document_id: str
    chunk_id: str
    entities: List[str] = []
    relationships: List[str] = []
    path: List[str] = []
    score: float


class QueryResponse(BaseModel):
    query_id: str
    query: str
    answer: str
    sources: List[Source]
    graph_paths: List[GraphPath]
    evidence: List[EvidenceObject] = []
    confidence: float
    intent: str
    intent_confidence: float
    retrieval_mode: str = "intent_routed"
    latency_ms: float = 0.0
    retrieval_metadata: RetrievalMetadata


class QueryHistoryItem(BaseModel):
    id: str
    query_text: str
    answer: Optional[str]
    intent: Optional[str]
    intent_confidence: Optional[float]
    answer_confidence: Optional[float]
    total_time_ms: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class VectorSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: Dict[str, Any] = {}


class TimelineEvent(BaseModel):
    id: str
    date: str
    title: str
    description: str
    entity_type: str
    entity_id: str


class AnalyticsOverview(BaseModel):
    total_documents: int
    total_entities: int
    total_relationships: int
    total_queries: int
    total_projects: int
    total_risks: int
    total_decisions: int
    avg_retrieval_time_ms: float

