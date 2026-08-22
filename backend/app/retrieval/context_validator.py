"""
MemoraGraph – Context Validator & Evidence Assembler

Ranks, deduplicates, filters, and formats vector text chunks
and graph path relationships into a consolidated context string.
Enforces size constraints to fit LLM limits.
"""

import logging
from typing import List, Dict, Any, Tuple
from app.schemas.query import Source, GraphPath

logger = logging.getLogger(__name__)


def validate_and_assemble_context(
    sources: List[Source],
    graph_paths: List[GraphPath],
    max_tokens: int = 1500,
) -> Tuple[str, List[Source]]:
    """
    Format vector chunks and graph relations into a clean context prompt.
    Deduplicates overlap, ranks by score, and formats graph paths.
    
    Returns:
        (formatted_context_string, clean_sources_list)
    """
    # 1. Deduplicate vector sources by text/chunk_id
    seen_texts = set()
    dedup_sources: List[Source] = []
    
    for s in sources:
        # Standardize text for simple dedup
        normalized_text = " ".join(s.text.strip().split()).lower()
        if normalized_text not in seen_texts:
            seen_texts.add(normalized_text)
            dedup_sources.append(s)

    # 2. Format Vector Text Context
    context_parts = []
    context_parts.append("=== DOCUMENT EVIDENCE ===")
    
    token_budget = max_tokens
    accumulated_tokens = 0

    for i, s in enumerate(dedup_sources):
        # Approximate tokens
        est_tokens = len(s.text) // 4
        if accumulated_tokens + est_tokens > token_budget * 0.7:  # save 30% for graph
            break
        
        doc_header = f"Source [{i+1}]: {s.document_name} (ID: {s.document_id}, Chunk ID: {s.chunk_id})"
        context_parts.append(f"{doc_header}\n{s.text.strip()}\n")
        accumulated_tokens += est_tokens

    # 3. Format Graph Paths Context
    if graph_paths:
        context_parts.append("=== KNOWLEDGE GRAPH RELATIONSHIPS ===")
        # Deduplicate identical path descriptions
        seen_paths = set()
        path_count = 0
        
        for gp in graph_paths:
            if not gp.description:
                continue
            if gp.description not in seen_paths:
                seen_paths.add(gp.description)
                # Parse node properties to give richer factual details
                details = []
                for node in gp.nodes:
                    props_str = ", ".join(f"{k}: {v}" for k, v in node.properties.items() if k != "name")
                    if props_str:
                        details.append(f"{node.type} '{node.label}' has attributes ({props_str})")
                
                detail_block = "\n  ".join(details)
                context_parts.append(
                    f"Path: {gp.description}\n"
                    f"  Details:\n  {detail_block}\n"
                )
                path_count += 1
                if path_count >= 8:  # limit total graph paths to avoid context bloating
                    break

    full_context = "\n".join(context_parts)
    logger.debug("Assembled context of size: %d characters", len(full_context))
    return full_context, dedup_sources


def validate_evidence(
    sources: List[Source],
    graph_paths: List[GraphPath],
    max_tokens: int = 1500,
) -> List[dict]:
    """
    Ranks, deduplicates, and filters vector search and graph path evidence.
    Enforces a token budget limit by retaining only high-scoring unique evidence.
    """
    evidence_list = []
    seen_texts = set()
    
    # 1. Map vector sources to EvidenceObjects
    for s in sources:
        norm_text = " ".join(s.text.strip().split()).lower()
        if norm_text in seen_texts:
            continue
        seen_texts.add(norm_text)
        
        doc_id = s.document_id
        chunk_id = s.chunk_id or ""
        
        evidence_list.append({
            "text": s.text,
            "source_document_id": doc_id,
            "chunk_id": chunk_id,
            "entities": [],
            "relationships": [],
            "path": [],
            "score": s.score
        })
        
    # 2. Map graph paths to EvidenceObjects
    for gp in graph_paths:
        if not gp.description:
            continue
        norm_desc = gp.description.lower()
        if norm_desc in seen_texts:
            continue
        seen_texts.add(norm_desc)
        
        # Resolve document provenance from nodes
        doc_id = "unknown-doc"
        chunk_id = ""
        for n in gp.nodes:
            if n.properties.get("source_document_id"):
                doc_id = n.properties["source_document_id"]
            if n.properties.get("source_chunk_id"):
                chunk_id = n.properties["source_chunk_id"]
                
        # Gather entity names and rel types
        entities = [n.label for n in gp.nodes]
        relationships = [e.type for e in gp.edges]
        path_seq = [f"{e.source} -[{e.type}]-> {e.target}" for e in gp.edges]
        
        # Graph path score (high priority relation)
        score = 0.90
        
        evidence_list.append({
            "text": gp.description,
            "source_document_id": doc_id,
            "chunk_id": chunk_id,
            "entities": entities,
            "relationships": relationships,
            "path": path_seq,
            "score": score
        })

    # Rank evidence list by score (descending)
    evidence_list.sort(key=lambda x: x["score"], reverse=True)
    
    # Context budget constraint: enforce token limit
    budget_evidence = []
    accumulated_tokens = 0
    
    for ev in evidence_list:
        est_tokens = len(ev["text"]) // 4
        if accumulated_tokens + est_tokens > max_tokens:
            logger.warning(
                "Context budget exceeded (%d > %d tokens). Truncating low-scoring evidence.",
                accumulated_tokens + est_tokens, max_tokens
            )
            break
        budget_evidence.append(ev)
        accumulated_tokens += est_tokens
        
    return budget_evidence
