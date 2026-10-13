"""
MemoraGraph – Academic Evaluation Harness & Retrieval Mode Validation Tests

Verifies:
1. Exactness of retrieval metrics (Precision@K, Document Recall@K, Retrieval F1, Path Precision@K, Bootstrap CI).
2. Multi-document & multi-chunk corpus verification:
   - More than one evaluation document exists.
   - More than two evaluation chunks exist.
   - Queries reference multiple documents and multiple chunks.
   - Ground-truth document and chunk IDs genuinely exist in the database.
   - Expected intents are valid and supported.
   - No duplicate query IDs exist.
3. Mode separation:
   - Vector RAG strictly never invokes Neo4j graph retrieval.
   - Standard GraphRAG performs unrestricted graph traversal (allowed_relationships=[]) without intent routing.
   - MemoraGraph executes intent classification and passes intent-specific allowed relationships.
4. Common dataset fairness: all three modes process identical query and ground-truth records.
5. Zero LLM calls are invoked during retrieval benchmarking.
"""

import json
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.evaluation.metrics import (
    calculate_precision_at_k,
    calculate_document_recall_at_k,
    calculate_f1_score,
    calculate_retrieval_f1_at_k,
    calculate_path_precision_at_k,
    calculate_answer_recall_at_k,
    calculate_answer_f1,
    bootstrap_confidence_interval,
)
from app.evaluation.runner import EvaluationRunner
from app.retrieval.intent_definitions import INTENT_DEFINITIONS
from app.schemas.query import Source, GraphPath, GraphNode, GraphEdge, IntentResult
from app.embeddings.vector_store import VectorSearchResult


# =====================================================================
# 1. Metric Calculation Unit Tests
# =====================================================================

def test_precision_at_k():
    retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    gt = ["doc1", "doc3"]
    # At k=1: "doc1" is in gt -> 1/1 = 1.0
    assert calculate_precision_at_k(retrieved, gt, k=1) == 1.0
    # At k=5: doc1, doc3 are in gt -> 2/5 = 0.4
    assert calculate_precision_at_k(retrieved, gt, k=5) == 0.4
    # Zero denominator / empty edge cases
    assert calculate_precision_at_k([], gt, k=5) == 0.0
    assert calculate_precision_at_k(retrieved, [], k=5) == 0.0
    assert calculate_precision_at_k(retrieved, gt, k=0) == 0.0


def test_document_recall_at_k():
    retrieved = ["doc1", "doc2", "doc4"]
    gt = ["doc1", "doc3"]
    # Retrieved 1 out of 2 ground truth docs -> 1/2 = 0.5
    assert calculate_document_recall_at_k(retrieved, gt, k=3) == 0.5
    # Retrieved both if doc3 present
    assert calculate_document_recall_at_k(["doc1", "doc3"], gt, k=5) == 1.0
    # Empty edge cases
    assert calculate_document_recall_at_k([], gt, k=5) == 0.0
    assert calculate_document_recall_at_k(retrieved, [], k=5) == 0.0


def test_retrieval_f1_score():
    # Harmonic mean of 0.4 and 1.0 -> 2 * 0.4 * 1.0 / 1.4 = 0.8 / 1.4 = 0.5714...
    f1 = calculate_retrieval_f1_at_k(0.4, 1.0)
    assert round(f1, 4) == 0.5714
    # Zero denominator safety
    assert calculate_retrieval_f1_at_k(0.0, 0.0) == 0.0
    assert calculate_f1_score(0.0, 0.0) == 0.0


def test_path_precision_at_k():
    retrieved_paths = [
        "(Project: Project Atlas) -[MANAGES]-> (Employee: Dr. Maya Rao)",
        "(Employee: Priya Nair) -[WORKS_IN]-> (Department: Core Architecture)",
    ]
    gt_paths = [
        "Dr. Maya Rao -[MANAGES]-> Project Atlas",
    ]
    # First path matches relationship and entities, second does not -> 1/2 = 0.5
    p_prec = calculate_path_precision_at_k(retrieved_paths, gt_paths, k=2)
    assert p_prec == 0.5
    # Zero denominator safety
    assert calculate_path_precision_at_k([], gt_paths, k=2) == 0.0
    assert calculate_path_precision_at_k(retrieved_paths, [], k=2) == 0.0


def test_answer_metrics():
    generated = "Dr. Maya Rao manages Project Atlas as the project director."
    gt_answers = ["Dr. Maya Rao", "Dr. Maya Rao manages Project Atlas"]
    rec = calculate_answer_recall_at_k(generated, gt_answers)
    f1 = calculate_answer_f1(generated, gt_answers)
    assert rec > 0.0
    assert f1 > 0.0
    # Empty safety
    assert calculate_answer_recall_at_k("", gt_answers) == 0.0
    assert calculate_answer_f1("", gt_answers) == 0.0


def test_bootstrap_confidence_interval():
    data = [0.4, 0.4, 0.4, 0.4, 0.4]
    mean, std, (ci_lower, ci_upper) = bootstrap_confidence_interval(data)
    assert round(mean, 2) == 0.4
    assert round(std, 2) == 0.0
    assert round(ci_lower, 2) == 0.4
    assert round(ci_upper, 2) == 0.4
    # Empty data safety
    assert bootstrap_confidence_interval([]) == (0.0, 0.0, (0.0, 0.0))


# =====================================================================
# 2. Dataset Integrity & Multi-Document Corpus Verification
# =====================================================================

def test_dataset_integrity():
    dataset_path = "./data/evaluation/synthetic_qa.json"
    assert os.path.exists(dataset_path), f"Dataset file must exist at {dataset_path}"
    runner = EvaluationRunner(dataset_path)
    assert len(runner.dataset) >= 30, f"Benchmark must contain at least 30 queries, got {len(runner.dataset)}"

    query_ids = []
    unique_doc_ids = set()
    unique_chunk_ids = set()

    for item in runner.dataset:
        q_id = item.get("id") or item.get("query_id")
        assert q_id, "Item must have an id"
        query_ids.append(q_id)

        intent = item.get("expected_intent") or item.get("intent")
        assert intent in INTENT_DEFINITIONS, f"Invalid intent: {intent}"

        doc_ids = item.get("relevant_document_ids") or item.get("ground_truth_document_ids") or []
        chunk_ids = item.get("relevant_chunk_ids") or item.get("ground_truth_chunk_ids") or []

        assert len(doc_ids) > 0, f"Query {q_id} must reference at least one document ID"
        assert len(chunk_ids) > 0, f"Query {q_id} must reference at least one chunk ID"

        for d in doc_ids:
            unique_doc_ids.add(d)
        for c in chunk_ids:
            unique_chunk_ids.add(c)

    # Verify no duplicate query IDs
    assert len(query_ids) == len(set(query_ids)), "Duplicate query IDs found in benchmark dataset"

    # Verify multiple documents exist in ground truth
    assert len(unique_doc_ids) > 1, f"Benchmark must cover multiple documents, got {len(unique_doc_ids)}"

    # Verify multiple chunks exist in ground truth
    assert len(unique_chunk_ids) > 2, f"Benchmark must cover multiple chunks, got {len(unique_chunk_ids)}"


@pytest.mark.asyncio
async def test_ground_truth_ids_exist_in_database():
    """Verify that every ground-truth document and chunk ID corresponds to actual indexed records."""
    from app.models.database import init_db, get_session
    from app.models.document import Document, DocumentChunk
    from sqlalchemy import select

    init_db(settings.database_url)
    session_gen = get_session()
    session = await anext(session_gen)

    db_docs = (await session.execute(select(Document))).scalars().all()
    db_chunks = (await session.execute(select(DocumentChunk))).scalars().all()

    existing_doc_ids = {d.id for d in db_docs}
    existing_chunk_ids = {c.id for c in db_chunks}

    assert len(existing_doc_ids) > 1, f"PostgreSQL must contain > 1 document, found {len(existing_doc_ids)}"
    assert len(existing_chunk_ids) > 2, f"PostgreSQL must contain > 2 chunks, found {len(existing_chunk_ids)}"

    with open("./data/evaluation/synthetic_qa.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    for item in dataset:
        doc_ids = item.get("relevant_document_ids") or item.get("ground_truth_document_ids") or []
        chunk_ids = item.get("relevant_chunk_ids") or item.get("ground_truth_chunk_ids") or []

        for did in doc_ids:
            assert did in existing_doc_ids, f"Ground-truth document ID '{did}' does not exist in database"
        for cid in chunk_ids:
            assert cid in existing_chunk_ids, f"Ground-truth chunk ID '{cid}' does not exist in database"


# =====================================================================
# 3. Retrieval Mode Separation & Fairness Tests (No LLM Calls)
# =====================================================================

@pytest.fixture
def mock_retrieval_dependencies():
    """Mocks vector store, encoder, and Neo4j to test orchestration without external service dependency."""
    mock_vec_results = [
        VectorSearchResult(
            document_id="doc-alpha-report",
            chunk_id="doc-alpha-report-c0",
            text="Arun manages Project Alpha in the Engineering department.",
            score=0.92,
            metadata={"project": "Project Alpha"},
            document_name="Project Alpha Report",
        )
    ]

    mock_graph_paths = [
        GraphPath(
            nodes=[
                GraphNode(id="n1", label="Arun", type="Employee"),
                GraphNode(id="n2", label="Project Alpha", type="Project"),
            ],
            edges=[
                GraphEdge(id="e1", source="n1", target="n2", type="MANAGES"),
            ],
            description="(Employee: Arun) -[MANAGES]-> (Project: Project Alpha)",
        )
    ]

    with patch("app.evaluation.runner.get_encoder") as mock_get_enc, \
         patch("app.evaluation.runner.get_vector_store") as mock_get_vs, \
         patch("app.evaluation.runner.GraphRetriever") as mock_graph_cls, \
         patch("app.evaluation.runner.get_intent_classifier") as mock_get_clf, \
         patch("app.evaluation.runner.get_hybrid_retriever") as mock_get_hr:

        # Mock encoder
        mock_enc = MagicMock()
        mock_enc.encode_single.return_value = [0.1] * 384
        mock_get_enc.return_value = mock_enc

        # Mock vector store
        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=mock_vec_results)
        mock_get_vs.return_value = mock_vs

        # Mock GraphRetriever instance
        mock_gr = MagicMock()
        mock_gr.retrieve_paths.return_value = mock_graph_paths
        mock_graph_cls.return_value = mock_gr

        # Mock HybridRetriever for seed candidates extraction
        mock_hr = MagicMock()
        mock_hr._extract_seed_entity_candidates.return_value = ["Project Alpha", "Arun"]
        mock_get_hr.return_value = mock_hr

        # Mock Intent Classifier
        mock_clf = MagicMock()
        mock_clf.classify.return_value = IntentResult(
            intent="PERSON_PROJECT",
            confidence=0.95,
            allowed_relationships=["MANAGES", "OWNS"],
            low_confidence=False,
            fallback_used=False,
        )
        mock_get_clf.return_value = mock_clf

        yield {
            "encoder": mock_enc,
            "vector_store": mock_vs,
            "graph_retriever": mock_gr,
            "classifier": mock_clf,
            "hybrid_retriever": mock_hr,
        }


@pytest.mark.asyncio
async def test_vector_rag_never_calls_neo4j(mock_retrieval_dependencies):
    """Verify Mode A (Vector RAG) executes vector retrieval only and strictly avoids Neo4j graph traversal."""
    runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
    mocks = mock_retrieval_dependencies

    res = await runner.execute_mode_retrieval(
        query="Who is the project manager for Project Alpha?",
        strategy="vector_rag",
        top_k=5,
    )

    # Vector store must be queried
    mocks["vector_store"].search.assert_called_once()
    # Neo4j GraphRetriever MUST NOT be called
    mocks["graph_retriever"].retrieve_paths.assert_not_called()
    # Graph metrics must be strictly zero
    assert res["graph_nodes_retrieved"] == 0
    assert res["graph_edges_traversed"] == 0
    assert res["retrieved_relationship_types"] == []
    assert res["graph_paths"] == []
    assert res["strategy"] == "vector_rag"


@pytest.mark.asyncio
async def test_standard_graphrag_does_not_use_intent_routing(mock_retrieval_dependencies):
    """Verify Mode B (Standard GraphRAG) traverses Neo4j with unrestricted allowed_relationships=[] and bypasses intent routing."""
    runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
    mocks = mock_retrieval_dependencies

    res = await runner.execute_mode_retrieval(
        query="Who is the project manager for Project Alpha?",
        strategy="standard_graphrag",
        top_k=5,
    )

    # Vector store queried
    mocks["vector_store"].search.assert_called_once()
    # Intent classifier MUST NOT be queried for intent routing in standard graphrag
    mocks["classifier"].classify.assert_not_called()
    # GraphRetriever MUST be called with allowed_relationships=[] (unrestricted)
    mocks["graph_retriever"].retrieve_paths.assert_called_once()
    call_args = mocks["graph_retriever"].retrieve_paths.call_args[1]
    assert call_args["allowed_relationships"] == [], "Standard GraphRAG must use unconstrained relationship traversal"
    assert res["graph_nodes_retrieved"] > 0
    assert res["graph_edges_traversed"] > 0
    assert res["strategy"] == "standard_graphrag"


@pytest.mark.asyncio
async def test_memoragraph_uses_intent_routed_traversal(mock_retrieval_dependencies):
    """Verify Mode C (MemoraGraph) classifies intent and passes allowed_relationships to directional graph retrieval."""
    runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
    mocks = mock_retrieval_dependencies

    res = await runner.execute_mode_retrieval(
        query="Who is the project manager for Project Alpha?",
        strategy="memoragraph",
        top_k=5,
    )

    # Intent classifier MUST be called
    mocks["classifier"].classify.assert_called_once_with("Who is the project manager for Project Alpha?")
    # Vector store queried
    mocks["vector_store"].search.assert_called_once()
    # GraphRetriever MUST be called with allowed_relationships from the classifier
    mocks["graph_retriever"].retrieve_paths.assert_called_once()
    call_args = mocks["graph_retriever"].retrieve_paths.call_args[1]
    assert call_args["allowed_relationships"] == ["MANAGES", "OWNS"]
    assert res["predicted_intent"] == "PERSON_PROJECT"
    assert res["intent_confidence"] == 0.95
    assert res["strategy"] == "memoragraph"


@pytest.mark.asyncio
async def test_all_modes_receive_same_query_and_ground_truth(mock_retrieval_dependencies):
    """Verify all three modes evaluate the identical queries from the benchmark dataset under identical top_k conditions."""
    runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
    sample_query = runner.dataset[0]["query"]
    
    for mode in ["vector_rag", "standard_graphrag", "memoragraph"]:
        res = await runner.execute_mode_retrieval(query=sample_query, strategy=mode, top_k=5)
        assert res["strategy"] == mode
        # All modes retrieve the same underlying document
        assert "doc-alpha-report" in res["retrieved_doc_ids"]
        assert "doc-alpha-report-c0" in res["retrieved_chunk_ids"]
        # Context tokens are estimated without LLM
        assert res["estimated_context_tokens"] > 0
        assert res["retrieval_latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_no_llm_calls_in_retrieval_benchmark(mock_retrieval_dependencies):
    """Verify that GroundedAnswerGenerator is strictly NEVER imported or invoked during retrieval evaluation."""
    runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
    with patch("app.llm.generator.get_answer_generator") as mock_gen:
        # Running mode retrieval must not touch LLM
        await runner.execute_mode_retrieval(
            query="Who manages Project Alpha?",
            strategy="vector_rag",
            top_k=5,
        )
        mock_gen.assert_not_called()
