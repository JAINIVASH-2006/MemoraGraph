"""
MemoraGraph – Grounded Answer Generator

Assembles system prompts, formats retrieved context (chunks & graph paths),
invokes the configured LLM provider, and extracts cited sources.
"""

import logging
import time
from typing import Tuple, List, Optional
import uuid

from app.config import settings
from app.llm.provider import get_llm_provider
from app.retrieval.hybrid_retriever import get_hybrid_retriever
from app.retrieval.graph_retriever import GraphRetriever
from app.retrieval.intent_classifier import get_intent_classifier
from app.retrieval.context_validator import validate_evidence
from app.schemas.query import QueryResponse, RetrievalMetadata, Source, GraphPath, IntentResult, EvidenceObject
from app.embeddings.encoder import get_encoder
from app.embeddings.vector_store import get_vector_store

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are MemoraGraph, an organizational knowledge assistant.

Answer the user's question ONLY using the supplied evidence.

Do not invent organizational facts.

Do not infer unsupported facts.

If the evidence does not contain enough information to answer the question, explicitly state that sufficient evidence was not found.

Use source information provided in the evidence when citing your answer.

Prefer concise, factual, evidence-grounded answers."""


class GroundedAnswerGenerator:
    """Coordinates retrieval, context assembly, LLM execution, and metrics extraction."""

    def __init__(self):
        self._retriever = get_hybrid_retriever()
        self._graph_retriever = GraphRetriever()
        self._llm = get_llm_provider()

    async def generate_answer(
        self,
        query: str,
        top_k: int = 5,
    ) -> QueryResponse:
        """
        Run the complete intent-routed Graph RAG pipeline.
        
        Args:
            query: User's query
            top_k: Number of vector chunks to retrieve
            
        Returns:
            QueryResponse schema containing answer, citations, and pipeline metrics.
        """
        query_id = str(uuid.uuid4())
        start_total = time.perf_counter()

        # 1. Intent routing
        start_classify = time.perf_counter()
        classifier = get_intent_classifier()
        intent_res = classifier.classify(query)
        classify_latency = (time.perf_counter() - start_classify) * 1000

        # Determine mode
        if intent_res.low_confidence:
            retrieval_mode = "fallback"
            allowed_rels = []
        else:
            retrieval_mode = "intent_routed"
            allowed_rels = intent_res.allowed_relationships

        # 2. Vector search to find entry seeds
        start_vector = time.perf_counter()
        encoder = get_encoder()
        query_emb = encoder.encode_single(query)
        vector_store = get_vector_store()
        vector_results = await vector_store.search(query_embedding=query_emb, top_k=top_k)
        vector_latency = (time.perf_counter() - start_vector) * 1000

        # Extract entry seeds using retriever candidates heuristic
        seed_names = self._retriever._extract_seed_entity_candidates(query, vector_results)

        # 3. Directed Graph Traversal
        start_graph = time.perf_counter()
        graph_paths = []
        if seed_names:
            graph_paths = self._graph_retriever.retrieve_paths(
                seed_entity_names=seed_names,
                allowed_relationships=allowed_rels,
                max_hops=2
            )
        graph_latency = (time.perf_counter() - start_graph) * 1000

        # Map to Sources for validator
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

        # 4. Context validation (ranking, deduplication, budget)
        start_val = time.perf_counter()
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
                score=e["score"]
            )
            for e in evidence_dicts
        ]
        val_latency = (time.perf_counter() - start_val) * 1000

        # 5. Format Evidence for Grounded Generation Prompt
        doc_evidence_parts = []
        graph_evidence_parts = []
        clean_sources = []
        clean_paths = []

        # Deduplicate sources based on validated evidence list
        for ev in evidence_objects:
            if ev.path:
                # Graph path evidence
                graph_evidence_parts.append(f"GRAPH PATH:\n{ev.text}")
                # Reconstruct original GraphPath object
                for gp in graph_paths:
                    if gp.description == ev.text and gp not in clean_paths:
                        clean_paths.append(gp)
            else:
                # Vector evidence
                doc_evidence_parts.append(
                    f"SOURCE:\n{ev.source_document_id}\n\n"
                    f"CHUNK:\n{ev.chunk_id}\n\n"
                    f"TEXT:\n{ev.text}"
                )
                for s in sources:
                    if s.chunk_id == ev.chunk_id and s not in clean_sources:
                        clean_sources.append(s)

        formatted_doc_evidence = "\n\n---\n\n".join(doc_evidence_parts) if doc_evidence_parts else "None"
        formatted_graph_evidence = "\n\n---\n\n".join(graph_evidence_parts) if graph_evidence_parts else "None"

        # 6. Assemble Prompt & Call LLM
        user_prompt = (
            f"SYSTEM INSTRUCTIONS\n"
            f"Answer the user's question ONLY using the supplied evidence.\n\n"
            f"USER QUESTION: {query}\n\n"
            f"DETECTED INTENT: {intent_res.intent}\n\n"
            f"RETRIEVAL MODE: {retrieval_mode}\n\n"
            f"VALIDATED EVIDENCE:\n"
            f"{formatted_doc_evidence}\n\n"
            f"GRAPH PATHS:\n"
            f"{formatted_graph_evidence}\n\n"
            f"SOURCE INFORMATION:\n"
            f"{', '.join(s.document_name for s in clean_sources) if clean_sources else 'None'}\n\n"
            f"Grounded Answer:"
        )

        start_gen = time.perf_counter()
        try:
            answer = await self._llm.complete(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_prompt,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            answer = f"Error generating answer: {str(e)}. Please check your API configuration."
        gen_latency = (time.perf_counter() - start_gen) * 1000
        total_latency = (time.perf_counter() - start_total) * 1000

        # Heuristic to compute grounding confidence based on answer content
        answer_lower = answer.lower()
        if any(term in answer_lower for term in ["sufficient evidence was not found", "cannot find", "not found", "insufficient evidence"]):
            confidence = 0.0
        else:
            base_score = 0.5
            if clean_sources:
                base_score += 0.3
            if clean_paths:
                base_score += 0.2
            confidence = min(1.0, base_score)

        meta = RetrievalMetadata(
            vector_chunks_retrieved=len(clean_sources),
            graph_nodes_retrieved=sum(len(p.nodes) for p in clean_paths),
            graph_edges_traversed=sum(len(p.edges) for p in clean_paths),
            retrieval_time_ms=round(vector_latency + graph_latency, 2),
            generation_time_ms=round(gen_latency, 2),
            total_time_ms=round(total_latency, 2),
            llm_model=settings.llm_model,
            fallback_used=intent_res.fallback_used,
        )

        return QueryResponse(
            query_id=query_id,
            query=query,
            answer=answer,
            sources=clean_sources,
            graph_paths=clean_paths,
            evidence=evidence_objects,
            confidence=round(confidence, 2),
            intent=intent_res.intent,
            intent_confidence=intent_res.confidence,
            retrieval_mode=retrieval_mode,
            latency_ms=round(total_latency, 2),
            retrieval_metadata=meta,
        )


# Singleton
_generator = None


def get_answer_generator() -> GroundedAnswerGenerator:
    global _generator
    if _generator is None:
        _generator = GroundedAnswerGenerator()
    return _generator
