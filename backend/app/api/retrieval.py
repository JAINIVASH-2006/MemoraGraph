"""
MemoraGraph API – Retrieval & Intent Classification Endpoints
"""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.embeddings.encoder import get_encoder
from app.embeddings.vector_store import get_vector_store
from app.retrieval.intent_classifier import get_intent_classifier
from app.models.user import User
from app.security.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["retrieval"])


class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class VectorSearchResponseItem(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict


class VectorSearchResponse(BaseModel):
    results: List[VectorSearchResponseItem]
    latency_ms: float


class IntentClassifyRequest(BaseModel):
    query: str = Field(..., min_length=1)


class IntentClassifyResponse(BaseModel):
    intent: str
    confidence: float
    allowed_relationships: List[str]
    low_confidence: bool
    latency_ms: float


@router.post("/retrieval/vector-search", response_model=VectorSearchResponse)
async def vector_search(
    body: VectorSearchRequest,
    current_user: User = Depends(get_current_user),
) -> VectorSearchResponse:
    """
    Perform a raw semantic vector search in Qdrant.
    Measures and logs embedding generation and search latencies.
    """
    start_time = time.perf_counter()
    
    try:
        # Measure embedding generation latency
        embed_start = time.perf_counter()
        encoder = get_encoder()
        query_emb = encoder.encode_single(body.query)
        embed_latency = (time.perf_counter() - embed_start) * 1000
        
        # Measure search latency
        search_start = time.perf_counter()
        vector_store = get_vector_store()
        results = await vector_store.search(query_embedding=query_emb, top_k=body.top_k)
        search_latency = (time.perf_counter() - search_start) * 1000
        
        total_latency = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "Vector search complete. Chunks: %d, Embed time: %.2fms, Search time: %.2fms, Total: %.2fms",
            len(results), embed_latency, search_latency, total_latency
        )
        
        response_items = [
            VectorSearchResponseItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.text,
                score=round(r.score, 4),
                metadata=r.metadata
            )
            for r in results
        ]
        
        return VectorSearchResponse(results=response_items, latency_ms=round(total_latency, 2))
        
    except Exception as e:
        logger.error("Vector search API failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {str(e)}"
        )


@router.post("/intent/classify", response_model=IntentClassifyResponse)
async def classify_intent(
    body: IntentClassifyRequest,
    current_user: User = Depends(get_current_user),
) -> IntentClassifyResponse:
    """
    Classifies the user query intent using SentenceTransformer prototype similarity.
    Measures and logs classification latency.
    """
    start_time = time.perf_counter()
    
    try:
        classifier = get_intent_classifier()
        intent_res = classifier.classify(body.query)
        
        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info("Intent classification completed in %.2fms", total_latency)
        
        return IntentClassifyResponse(
            intent=intent_res.intent,
            confidence=intent_res.confidence,
            allowed_relationships=intent_res.allowed_relationships,
            low_confidence=intent_res.low_confidence,
            latency_ms=round(total_latency, 2)
        )
        
    except Exception as e:
        logger.error("Intent classification API failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intent classification failed: {str(e)}"
        )


# Import GraphPath and EvidenceObject from schema
from app.schemas.query import GraphPath, EvidenceObject

class GraphSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)

class GraphSearchResponse(BaseModel):
    query: str
    intent: str
    confidence: float
    retrieval_mode: str
    seed_entities: List[str]
    paths: List[GraphPath]
    evidence: List[EvidenceObject]
    latency_ms: float


@router.post("/retrieval/graph-search", response_model=GraphSearchResponse)
async def graph_search(
    body: GraphSearchRequest,
    current_user: User = Depends(get_current_user),
) -> GraphSearchResponse:
    """
    Perform a constrained/fallback graph retrieval and context validation.
    """
    start_time = time.perf_counter()
    
    try:
        from app.retrieval.hybrid_retriever import get_hybrid_retriever
        from app.retrieval.graph_retriever import GraphRetriever
        from app.retrieval.context_validator import validate_evidence
        from app.schemas.query import Source
        from app.config import settings

        # 1. Classify Intent
        classifier = get_intent_classifier()
        intent_res = classifier.classify(body.query)
        
        # Determine mode
        if intent_res.low_confidence:
            retrieval_mode = "fallback"
            allowed_rels = []  # broader graph search
        else:
            retrieval_mode = "intent_routed"
            allowed_rels = intent_res.allowed_relationships

        # 2. Vector Search (Seed Entities Identification context)
        encoder = get_encoder()
        query_emb = encoder.encode_single(body.query)
        vector_store = get_vector_store()
        vector_results = await vector_store.search(query_embedding=query_emb, top_k=body.top_k)
        
        # 3. Extract Seed Entities using HybridRetriever heuristic
        hybrid_retriever = get_hybrid_retriever()
        seed_entities = hybrid_retriever._extract_seed_entity_candidates(body.query, vector_results)
        
        # 4. Traversal
        graph_retriever = GraphRetriever()
        graph_paths = []
        if seed_entities:
            graph_paths = graph_retriever.retrieve_paths(
                seed_entity_names=seed_entities,
                allowed_relationships=allowed_rels,
                max_hops=2
            )
            
        # Map vector search results to Source schemas
        sources = [
            Source(
                document_id=r.document_id,
                document_name=r.document_name,
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                source_type="vector"
            )
            for r in vector_results
        ]
        
        # 5. Context Validation (ranking, deduplication, budget constraints)
        evidence_dicts = validate_evidence(
            sources=sources,
            graph_paths=graph_paths,
            max_tokens=settings.max_context_tokens
        )
        
        evidence_objects = [
            EvidenceObject(
                text=e["text"],
                source_document_id=e["source_document_id"],
                chunk_id=e["chunk_id"],
                entities=e["entities"],
                relationships=e["relationships"],
                path=e["path"],
                score=round(e["score"], 4)
            )
            for e in evidence_dicts
        ]
        
        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Graph G-RAG retrieval complete. Mode: %s, Seeds: %d, Paths: %d, Evidence: %d, Latency: %.2fms",
            retrieval_mode, len(seed_entities), len(graph_paths), len(evidence_objects), total_latency
        )
        
        return GraphSearchResponse(
            query=body.query,
            intent=intent_res.intent,
            confidence=intent_res.confidence,
            retrieval_mode=retrieval_mode,
            seed_entities=seed_entities,
            paths=graph_paths,
            evidence=evidence_objects,
            latency_ms=round(total_latency, 2)
        )
        
    except Exception as e:
        logger.error("Graph search API failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph search retrieval failed: {str(e)}"
        )
