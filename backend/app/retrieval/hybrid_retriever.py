"""
MemoraGraph – Hybrid Vector-Graph Retriever

Orchestrates the entire MemoraGraph retrieval workflow:
1. Vector search in Qdrant (top chunks)
2. Semantic intent classification (intent + allowed relations)
3. Entity extraction from query & top chunks (as entry points)
4. Constrained directed graph traversal in Neo4j
5. Formats outputs for context validation
"""

import logging
import time
from typing import List, Dict, Any, Tuple, Optional

from app.embeddings.encoder import get_encoder
from app.embeddings.vector_store import get_vector_store, VectorSearchResult
from app.retrieval.intent_classifier import get_intent_classifier
from app.retrieval.graph_retriever import GraphRetriever
from app.schemas.query import IntentResult, Source, GraphPath

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Orchestrator for intent-routed vector and graph memory retrieval."""

    def __init__(self):
        self._encoder = get_encoder()
        self._vector_store = get_vector_store()
        self._graph_retriever = GraphRetriever()

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Source], List[GraphPath], IntentResult]:
        """
        Run the hybrid MemoraGraph retrieval pipeline with user isolation.
        
        Returns:
            (sources, graph_paths, intent_result)
        """
        logger.info("Starting hybrid retrieval for query: '%s' (user_id=%s)", query, user_id)

        # 1. Intent Classification
        classifier = get_intent_classifier()
        intent_res = classifier.classify(query)

        # 2. Vector Search (for textual chunks)
        query_emb = self._encoder.encode_single(query)
        vector_results: List[VectorSearchResult] = await self._vector_store.search(
            query_embedding=query_emb,
            top_k=top_k,
            filter_user_id=user_id,
        )

        sources = [
            Source(
                document_id=r.document_id,
                document_name=r.document_name,
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                source_type="vector",
            )
            for r in vector_results
        ]

        # 3. Extract seed entities from query and vector chunks for Neo4j entry points
        seed_names = self._extract_seed_entity_candidates(query, vector_results)

        # 4. Directed Graph Traversal
        graph_paths = []
        if seed_names:
            graph_paths = self._graph_retriever.retrieve_paths(
                seed_entity_names=seed_names,
                allowed_relationships=intent_res.allowed_relationships,
                max_hops=2,
                user_id=user_id,
            )

        return sources, graph_paths, intent_res

    def _extract_seed_entity_candidates(
        self,
        query: str,
        vector_results: List[VectorSearchResult],
    ) -> List[str]:
        """
        Extract candidate entity names to seed the graph search.
        Uses capitalization heuristics, quotes, and project names.
        """
        candidates = set()

        # Heuristic 1: Extract capitalized words/phrases from query
        # Avoid common sentence starters
        words = query.strip().split()
        if len(words) > 1:
            # Match capitalized phrases (e.g. "Project Alpha", "Arun")
            import re
            phrases = re.findall(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\b", query)
            for p in phrases:
                if p.lower() not in ("who", "what", "where", "when", "why", "how", "project", "the", "a", "an", "i"):
                    candidates.add(p)

        # Heuristic 2: Words in quotes (e.g. 'Project Alpha')
        quotes = re.findall(r"['\"](.+?)['\"]", query)
        for q in quotes:
            candidates.add(q)

        # Heuristic 3: Explicit project prefixes
        proj_match = re.search(r"[Pp]roject\s+([A-Z][a-zA-Z0-9]*)", query)
        if proj_match:
            candidates.add(f"Project {proj_match.group(1)}")
            candidates.add(proj_match.group(1))

        # Heuristic 4: Get metadata entities (projects/departments) from top vector search results
        for r in vector_results:
            meta = r.metadata
            if meta.get("project"):
                candidates.add(meta["project"])
            if meta.get("department"):
                candidates.add(meta["department"])
            if meta.get("author"):
                candidates.add(meta["author"])

        candidate_list = list(candidates)
        logger.debug("Extracted seed candidates for graph: %s", candidate_list)
        return candidate_list


# Singleton
_hybrid_retriever = None


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever
