"""
MemoraGraph – Phase 6 LLM Generation & Grounded Answer End-to-End Tests
"""

import pytest
import os
import sys
import time

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.embeddings.encoder import get_encoder, init_encoder, _encoder_instance
from app.embeddings.vector_store import get_vector_store, init_vector_store
from app.graph.neo4j_client import get_neo4j, init_neo4j
from app.llm.generator import get_answer_generator
from app.retrieval.intent_classifier import get_intent_classifier
from app.config import settings


@pytest.fixture(autouse=True)
def setup_services():
    """Initialize all RAG services for end-to-end verification."""
    global _encoder_instance
    if _encoder_instance is None:
        init_encoder(settings.embedding_model)
        
    init_vector_store(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection
    )
    
    init_neo4j(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password
    )
    
    # Pre-cache intent prototypes
    get_intent_classifier()
    
    # Initialize LLM provider
    from app.llm.provider import init_llm_provider, _llm_provider_instance
    if _llm_provider_instance is None:
        init_llm_provider(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model
        )


@pytest.mark.asyncio
async def test_end_to_end_grounded_rag_queries():
    """Test full e2e RAG pipeline with actual queries and verify groundedness and latency."""
    generator = get_answer_generator()
    
    test_queries = [
        "What risks affected Project Alpha?",
        "Who managed Project Alpha?",
        "What decision resolved the security risk?",
        "What was the outcome of the decision?",
        "What technology was used in Project Alpha?",
        "What information is unavailable?"
    ]
    
    print("\n\n" + "="*80)
    print("                      PHASE 6 E2E GROUNDED GENERATION REPORT")
    print("="*80)
    
    for q in test_queries:
        start_time = time.perf_counter()
        response = await generator.generate_answer(q, top_k=5)
        latency = (time.perf_counter() - start_time) * 1000
        
        print(f"\nQuery: '{q}'")
        print(f"  Intent: {response.intent} (Confidence: {response.intent_confidence:.3f})")
        print(f"  Retrieval Mode: {response.retrieval_mode}")
        print(f"  Sources Cited: {[s.document_name for s in response.sources]}")
        print(f"  Graph Paths: {len(response.graph_paths)}")
        print(f"  Validated Evidence Items: {len(response.evidence)}")
        print(f"  Answer: {response.answer}")
        print(f"  Answer Confidence: {response.confidence:.2f}")
        print(f"  Latency: {latency:.2f}ms")
        
        # Validations
        assert response.answer is not None
        assert isinstance(response.sources, list)
        assert isinstance(response.graph_paths, list)
        
        # Grounding checks: sources must exist in evidence
        for source in response.sources:
            matched = any(ev.source_document_id == source.document_id for ev in response.evidence)
            assert matched is True, f"Cited source {source.document_name} was not present in validated evidence!"
            
    print("="*80 + "\n")


@pytest.mark.asyncio
async def test_hallucination_prevention():
    """Test that queries asking for non-existent facts do not cause hallucination."""
    generator = get_answer_generator()
    
    hallucination_query = "What was the salary of the CEO of Project Alpha?"
    
    response = await generator.generate_answer(hallucination_query, top_k=5)
    
    print("\n" + "="*80)
    print("                      HALLUCINATION PREVENTION TEST")
    print("="*80)
    print(f"Query: '{hallucination_query}'")
    print(f"Answer: {response.answer}")
    print(f"Confidence: {response.confidence:.2f}")
    print("="*80 + "\n")
    
    # Verify that the model did not make up a salary and declared insufficient info
    answer_lower = response.answer.lower()
    assert any(term in answer_lower for term in ["sufficient evidence", "not found", "cannot find", "not contain", "insufficient"])
    assert response.confidence == 0.0
