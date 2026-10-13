"""
MemoraGraph – Grounded Answer Generator

Assembles system prompts, formats retrieved context (chunks & graph paths),
invokes the configured LLM provider, and extracts cited sources.
"""

import logging
import re
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

MULTI_PART_INSTRUCTIONS = """
The question may contain multiple requests. Answer every distinct request explicitly,
using a short numbered list with these labels when applicable: Cause, Resolver, and
Resolution evidence. If a requested fact is not supported by the supplied evidence,
say so for that item instead of omitting it. Keep facts from different incidents or
documents separate; do not combine unrelated sources into one answer.
"""


class GroundedAnswerGenerator:
    """Coordinates retrieval, context assembly, LLM execution, and metrics extraction."""

    def __init__(self):
        self._retriever = get_hybrid_retriever()
        self._graph_retriever = GraphRetriever()
        self._llm = get_llm_provider()

    @staticmethod
    def _cohere_vector_results(vector_results, query: str = ""):
        """Filter vector results to align with the specific entity queried, or dominant source document."""
        if not vector_results:
            return vector_results

        query_lower = (query or "").lower()
        target_projects = [p.lower() for p in re.findall(r"[Pp]roject\s+([A-Za-z0-9_-]+)", query)]
        target_ids = [i.lower() for i in re.findall(r"\b([A-Z]{2,5}-\d{2,5})\b", query)]

        # If query specifically targets a named project, filter out vector results from competing projects
        if target_projects:
            matched = [
                r for r in vector_results
                if any(tp in r.text.lower() or tp in (r.document_name or "").lower() for tp in target_projects)
            ]
            if matched:
                return matched

        if target_ids:
            matched = [
                r for r in vector_results
                if any(tid in r.text.lower() or tid in (r.document_name or "").lower() for tid in target_ids)
            ]
            if matched:
                return matched

        if len(vector_results) < 3:
            return vector_results

        counts = {}
        for result in vector_results:
            counts[result.document_id] = counts.get(result.document_id, 0) + 1

        top_document_id = vector_results[0].document_id
        top_count = counts[top_document_id]
        other_count = max((count for doc_id, count in counts.items() if doc_id != top_document_id), default=0)
        if top_count < 2 or top_count <= other_count:
            return vector_results

        logger.info(
            "Restricting answer context to dominant document %s (%d/%d vector results)",
            top_document_id,
            top_count,
            len(vector_results),
        )
        return [result for result in vector_results if result.document_id == top_document_id]

    @staticmethod
    def _build_fact_role_check(query: str, evidence_objects: List[EvidenceObject]) -> str:
        """Expose concise evidence excerpts for each role in a multi-part query."""
        query_lower = query.lower()
        lines = []
        for evidence in evidence_objects:
            lines.extend(line.strip() for line in evidence.text.splitlines() if line.strip())

        def matching_lines(keywords):
            return list(dict.fromkeys(
                line for line in lines if any(keyword in line.lower() for keyword in keywords)
            ))[:3]

        sections = []
        if any(term in query_lower for term in ("cause", "caused", "why", "reason")):
            cause_lines = matching_lines(("cause", "caused", "identified", "incorrect", "because", "due"))
            if cause_lines:
                sections.append("CAUSE EVIDENCE:\n" + "\n".join(f"- {line}" for line in cause_lines))
        if "who" in query_lower and any(term in query_lower for term in ("resolve", "resolved", "fix", "correct")):
            resolver_lines = matching_lines(("corrected", "fixed", "implemented", "responsible", "owner"))
            if resolver_lines:
                sections.append("CORRECTIVE ACTOR EVIDENCE (not merely a verifier):\n" + "\n".join(f"- {line}" for line in resolver_lines))
        if any(term in query_lower for term in ("evidence", "confirm", "proof", "check")):
            confirmation_lines = matching_lines(("evidence", "confirmed", "passed", "successful", "verified", "logs", "checks"))
            if confirmation_lines:
                sections.append("RESOLUTION EVIDENCE:\n" + "\n".join(f"- {line}" for line in confirmation_lines))

        return "\n\n".join(sections) or "None"

    @staticmethod
    def _append_missing_fact_evidence(answer: str, query: str, evidence_objects: List[EvidenceObject]) -> str:
        """Keep a one-call answer from silently omitting distinctive supported facts."""
        answer_lower = answer.lower()
        lines = [
            line.strip()
            for evidence in evidence_objects
            for line in evidence.text.splitlines()
            if line.strip()
        ]
        additions = []

        if any(term in query.lower() for term in ("cause", "caused", "why", "reason")):
            cause_lines = [line for line in lines if any(term in line.lower() for term in ("incorrect", "audience", "identified", "rejected"))]
            cause_terms = {term for term in ("incorrect", "audience", "rejected") if any(term in line.lower() for line in cause_lines)}
            if cause_lines and len(cause_terms & set(re.findall(r"[a-z]+", answer_lower))) < 2:
                additions.append("Cause evidence: " + cause_lines[0])

        if "who" in query.lower() and any(term in query.lower() for term in ("resolve", "resolved", "fix", "correct")):
            resolver_lines = [line for line in lines if any(term in line.lower() for term in ("corrected", "fixed", "implemented", "responsible"))]
            names = set()
            for line in resolver_lines:
                names.update(re.findall(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", line))
            if resolver_lines and not any(name.lower() in answer_lower for name in names):
                additions.append("Corrective actor evidence: " + resolver_lines[0])

        if additions:
            return answer.rstrip() + "\n\nAdditional evidence for omitted details:\n- " + "\n- ".join(additions)
        return answer

    async def generate_answer(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        retrieval_strategy: str = "memoragraph",
    ) -> QueryResponse:
        """
        Run the complete intent-routed Graph RAG pipeline with user isolation.
        
        Args:
            query: User's query
            top_k: Number of vector chunks to retrieve
            user_id: Optional user ID for tenant isolation
            retrieval_strategy: 'memoragraph' (intent-routed), 'vector_rag' (vector only), or 'standard_graphrag' (unrouted graph)
            
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

        # Determine retrieval mode & allowed relationships based on strategy
        if retrieval_strategy == "vector_rag":
            retrieval_mode = "vector_rag"
            allowed_rels = []
        elif retrieval_strategy == "standard_graphrag":
            retrieval_mode = "standard_graphrag"
            allowed_rels = []  # unconstrained, traverses all graph relationships
        else:
            if intent_res.low_confidence:
                retrieval_mode = "fallback"
                allowed_rels = []
            else:
                retrieval_mode = "intent_routed"
                allowed_rels = intent_res.allowed_relationships

        start_vector = time.perf_counter()
        vector_results = []
        try:
            encoder = get_encoder()
            query_emb = encoder.encode_single(query)
            vector_store = get_vector_store()
            vector_results = await vector_store.search(
                query_embedding=query_emb,
                top_k=top_k,
                filter_user_id=user_id,
            )
        except Exception as e:
            logger.warning("Vector search unavailable during query generation: %s", e)
        vector_latency = (time.perf_counter() - start_vector) * 1000
        vector_results = self._cohere_vector_results(vector_results, query=query)

        # Extract entry seeds using retriever candidates heuristic
        seed_names = []
        graph_paths = []
        graph_latency = 0.0

        if retrieval_strategy != "vector_rag":
            seed_names = self._retriever._extract_seed_entity_candidates(query, vector_results)

            # 3. Directed graph traversal from seeds
            start_graph = time.perf_counter()
            if seed_names:
                graph_paths = self._graph_retriever.retrieve_paths(
                    seed_entity_names=seed_names,
                    allowed_relationships=allowed_rels,
                    max_hops=2,
                    user_id=user_id,
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
            max_tokens=settings.max_context_tokens,
            query=query,
            is_fallback=(retrieval_mode == "fallback"),
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

        if not evidence_objects:
            answer = "Sufficient evidence was not found in the indexed documents to answer the question."
            total_latency = (time.perf_counter() - start_total) * 1000
            meta = RetrievalMetadata(
                vector_chunks_retrieved=0,
                graph_nodes_retrieved=0,
                graph_edges_traversed=0,
                retrieval_time_ms=round(vector_latency + graph_latency, 2),
                generation_time_ms=0.0,
                total_time_ms=round(total_latency, 2),
                llm_model=settings.llm_model,
                fallback_used=intent_res.fallback_used,
            )
            return QueryResponse(
                query_id=query_id,
                query=query,
                answer=answer,
                sources=[],
                graph_paths=[],
                evidence=[],
                confidence=0.0,
                intent=intent_res.intent,
                intent_confidence=intent_res.confidence,
                retrieval_mode=retrieval_mode,
                latency_ms=round(total_latency, 2),
                retrieval_metadata=meta,
            )

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
        fact_role_check = self._build_fact_role_check(query, evidence_objects)

        # Select prompt instructions based on query intent and structure
        is_incident_query = any(term in query.lower() for term in ("cause", "why", "who", "resolve", "resolved", "incident", "inc-", "fix", "error", "outage"))

        # 6. Assemble Prompt & Call LLM
        prompt_parts = [
            f"USER QUESTION: {query}",
            f"DETECTED INTENT: {intent_res.intent}",
            f"RETRIEVAL MODE: {retrieval_mode}",
            f"VALIDATED EVIDENCE:\n{formatted_doc_evidence}",
            f"GRAPH PATHS:\n{formatted_graph_evidence}",
        ]
        if is_incident_query:
            prompt_parts.append(f"FACT ROLE CHECK:\n{fact_role_check}")
            prompt_parts.append(MULTI_PART_INSTRUCTIONS)
        else:
            def_instructions = (
                "Provide a direct, concise, factual definition or answer to the question using ONLY the supplied evidence.\n"
                "Do not introduce unrelated incidents, projects, or people.\n"
                "If the evidence does not contain sufficient information to answer the question, explicitly state: 'Sufficient evidence was not found.'"
            )
            prompt_parts.append(def_instructions)
        prompt_parts.append("Grounded Answer:")

        user_prompt = "\n\n".join(prompt_parts)

        start_gen = time.perf_counter()
        try:
            answer = await self._llm.complete(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_prompt,
                temperature=settings.llm_temperature,
                max_tokens=512,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            answer = f"Error generating answer: {str(e)}. Please check your API configuration."
        if not answer.startswith("Error generating answer"):
            answer = self._append_missing_fact_evidence(answer, query, evidence_objects)
        gen_latency = (time.perf_counter() - start_gen) * 1000
        total_latency = (time.perf_counter() - start_total) * 1000

        # Heuristic to compute grounding confidence based on answer content
        answer_lower = answer.lower()
        if any(term in answer_lower for term in ["sufficient evidence was not found", "cannot find", "not found", "insufficient evidence"]) or answer.startswith("Error generating answer"):
            confidence = 0.0
        else:
            base_score = 0.5
            if clean_sources:
                base_score += 0.3
            if clean_paths:
                base_score += 0.2
            confidence = min(1.0, base_score)

        prompt_tokens = None
        completion_tokens = None
        if hasattr(self._llm, "get_last_token_usage"):
            usage = self._llm.get_last_token_usage()
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")

        meta = RetrievalMetadata(
            vector_chunks_retrieved=len(clean_sources),
            graph_nodes_retrieved=sum(len(p.nodes) for p in clean_paths),
            graph_edges_traversed=sum(len(p.edges) for p in clean_paths),
            retrieval_time_ms=round(vector_latency + graph_latency, 2),
            generation_time_ms=round(gen_latency, 2),
            total_time_ms=round(total_latency, 2),
            llm_model=settings.llm_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
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
