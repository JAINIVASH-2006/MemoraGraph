"""
MemoraGraph – Context Validator & Evidence Assembler

Ranks, deduplicates, filters, and formats vector text chunks
and graph path relationships into a consolidated context string.
Enforces size constraints to fit LLM limits.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
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


def extract_relevant_context(chunk_text: str, query: str, max_chars: int = 1500) -> str:
    """
    Extracts relevant sentences/lines matching query keywords, prioritizing
    definition lines for overview queries and incident lines for cause/resolution queries.
    Preserves factual grounding and document provenance.
    """
    if len(chunk_text) <= max_chars:
        return chunk_text

    stop_words = {"who", "what", "where", "when", "why", "how", "the", "a", "an", "is", "are", "was", "were", "this", "that", "for", "with", "between", "and"}
    query_words = set(w.lower().strip("?,.!") for w in query.split() if len(w) > 2 and w.lower() not in stop_words)
    query_lower = query.lower()

    lines = [line.strip() for line in chunk_text.split("\n") if line.strip()]
    
    # Detect query focus
    is_cause_query = any(term in query_lower for term in ("cause", "caused", "why", "reason", "root cause"))
    is_resolution_query = any(term in query_lower for term in ("resolve", "resolved", "fix", "fixed", "correct", "action", "who resolved"))
    is_def_query = any(term in query_lower for term in ("what is", "overview", "explain", "describe", "relationship", "relation", "platform", "component"))

    priority_terms = []
    if is_cause_query:
        priority_terms.extend(["cause", "caused", "root cause", "incorrect", "due to", "because", "symptom"])
    if is_resolution_query:
        priority_terms.extend(["resolved", "resolved by", "corrected", "fixed", "verification", "verified by", "solution", "action"])
    if is_def_query:
        priority_terms.extend(["overview", "is a", "is an", "consists of", "platform", "project", "depends on", "service", "architecture"])

    # 1. Exact query match lines (highest relevance)
    direct_match_lines = [line for line in lines if any(w in line.lower() for w in query_words)]
    
    # 2. Priority terms lines
    priority_lines = [line for line in lines if any(term in line.lower() for term in priority_terms)]
    
    # Combine matches with direct query matches first
    selected_lines = list(dict.fromkeys(direct_match_lines + priority_lines))
    if not selected_lines:
        return chunk_text[:max_chars]

    assembled = []
    current_len = 0
    for line in selected_lines:
        if current_len + len(line) + 1 <= max_chars:
            assembled.append(line)
            current_len += len(line) + 1
        else:
            break
            
    return "\n".join(assembled) if assembled else chunk_text[:max_chars]


def validate_evidence(
    sources: List[Source],
    graph_paths: List[GraphPath],
    max_tokens: int = 1500,
    query: Optional[str] = None,
    is_fallback: bool = False,
) -> List[dict]:
    """
    Ranks, deduplicates, and filters vector search and graph path evidence.
    Enforces entity-relevance guardrails to prevent unrelated projects or incidents
    from contaminating evidence for a specific queried entity.
    """
    import re
    evidence_list = []
    seen_texts = set()

    # Identify any specific project names or entity IDs explicitly requested in query
    target_projects = []
    target_ids = []
    query_lower = (query or "").lower()
    if query:
        target_projects = [p.lower() for p in re.findall(r"[Pp]roject\s+([A-Za-z0-9_-]+)", query)]
        target_ids = [i.lower() for i in re.findall(r"\b([A-Z]{2,5}-\d{2,5})\b", query)]

    # 1. Map vector sources to EvidenceObjects with relevance filtering
    for s in sources:
        norm_text = " ".join(s.text.strip().split()).lower()
        if norm_text in seen_texts:
            continue

        # Relevance guardrail: If query targets a specific project, verify chunk relevance
        if target_projects:
            chunk_text_lower = s.text.lower()
            doc_name_lower = (s.document_name or "").lower()
            # If chunk is from a known different project and contains none of the target projects, filter it out
            matches_target = any(tp in chunk_text_lower or tp in doc_name_lower for tp in target_projects)
            if not matches_target and any(f"project {tp}" in query_lower for tp in target_projects):
                # Discard chunks about other projects that have zero mention of the target project
                continue

        # Relevance guardrail: If query targets a specific incident/entity ID (e.g. INC-301)
        if target_ids:
            chunk_text_lower = s.text.lower()
            doc_name_lower = (s.document_name or "").lower()
            matches_id = any(tid in chunk_text_lower or tid in doc_name_lower for tid in target_ids)
            if not matches_id:
                # If chunk does not mention the target ID, drop it to avoid incident confusion
                continue

        seen_texts.add(norm_text)
        doc_id = s.document_id
        chunk_id = s.chunk_id or ""

        chunk_content = s.text
        if query and (is_fallback or len(s.text) > 1500):
            chunk_content = extract_relevant_context(s.text, query)

        evidence_list.append({
            "text": chunk_content,
            "source_document_id": doc_id,
            "chunk_id": chunk_id,
            "entities": [],
            "relationships": [],
            "path": [],
            "score": s.score
        })
        
    # 2. Map graph paths to EvidenceObjects with relevance filtering
    for gp in graph_paths:
        if not gp.description:
            continue
        norm_desc = gp.description.lower()
        if norm_desc in seen_texts:
            continue

        # Relevance guardrail: If query targets a specific project or ID, ensure graph path touches it
        if target_projects:
            path_touches_target = any(
                tp in norm_desc or any(tp in n.label.lower() for n in gp.nodes)
                for tp in target_projects
            )
            if not path_touches_target:
                # Discard graph paths from other projects
                continue

        if target_ids:
            path_touches_id = any(
                tid in norm_desc or any(tid in n.label.lower() for n in gp.nodes)
                for tid in target_ids
            )
            if not path_touches_id:
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
                
        entities = [n.label for n in gp.nodes]
        relationships = [e.type for e in gp.edges]
        path_seq = [f"{e.source} -[{e.type}]-> {e.target}" for e in gp.edges]
        
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
