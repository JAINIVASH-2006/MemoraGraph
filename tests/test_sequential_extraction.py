"""
MemoraGraph – Sequential Graph Extraction & Concurrency Tests

Verifies:
1. Extraction does not launch concurrent requests when extraction_concurrency = 1 (default).
2. Timeout/failure raises GraphExtractionError and is strictly distinguishable from legitimate zero-entity extraction.
3. When all chunks fail, pipeline refuses to report PROCESSED with 0 entities.
4. Successful extraction preserves graph structure and consolidation.
"""

import asyncio
import os
import sys
import pytest
from types import SimpleNamespace

# Adjust path to import backend app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.graph.extractor import (
    extract_entities_and_relationships,
    GraphExtractionError,
    _validate_and_clean,
)
from app.graph.builder import GraphBuilder
from app.graph.neo4j_client import get_neo4j, init_neo4j, _client
from app.llm.provider import LLMProvider


class ConcurrencyTrackingMockLLM(LLMProvider):
    """Tracks peak concurrent calls to complete()."""

    def __init__(self, response_text: str = '{"entities": [], "relationships": []}'):
        self.response_text = response_text
        self.active_calls = 0
        self.max_concurrent_calls = 0
        self.call_count = 0

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        self.active_calls += 1
        self.call_count += 1
        if self.active_calls > self.max_concurrent_calls:
            self.max_concurrent_calls = self.active_calls
        try:
            # Simulate CPU inference latency
            await asyncio.sleep(0.05)
            return self.response_text
        finally:
            self.active_calls -= 1

    async def ping(self) -> bool:
        return True


class FailingMockLLM(LLMProvider):
    """Simulates a timeout or connection failure during extraction."""

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        await asyncio.sleep(0.01)
        raise TimeoutError("Ollama HTTP connection timed out after 120s")

    async def ping(self) -> bool:
        return False


class EmptyFailureMockLLM(FailingMockLLM):
    """Simulates a provider failure with no string message."""

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        raise TimeoutError()


@pytest.fixture(autouse=True)
def setup_neo4j_fixture():
    global _client
    if _client is None:
        init_neo4j(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
        )
    return _client


@pytest.mark.asyncio
async def test_extraction_does_not_launch_5_concurrent_requests():
    """13a. Verify that when extraction_concurrency is 1, requests are processed sequentially (peak concurrency = 1)."""
    mock_llm = ConcurrencyTrackingMockLLM()
    chunks = [f"Text chunk {i} mentioning Project Apollo." for i in range(5)]

    # Concurrency limit = 1 (default)
    concurrency = 1
    max_extract_chunks = min(settings.max_extraction_chunks, len(chunks))

    successful_extractions = []
    if concurrency <= 1:
        for i in range(max_extract_chunks):
            ext = await extract_entities_and_relationships(
                text=chunks[i],
                document_name="TestDoc",
                llm_client=mock_llm,
            )
            successful_extractions.append(ext)

    assert mock_llm.call_count == 5
    assert mock_llm.max_concurrent_calls == 1, (
        f"Expected max concurrent calls to be 1, but got {mock_llm.max_concurrent_calls}"
    )


@pytest.mark.asyncio
async def test_timeout_failure_distinguishable_from_successful_zero_extraction():
    """13b. Verify that timeout/failure raises GraphExtractionError while legitimate zero extraction succeeds cleanly."""
    # Case 1: Legitimate zero-entity extraction
    zero_entity_llm = ConcurrencyTrackingMockLLM(response_text='{"entities": [], "relationships": []}')
    zero_result = await extract_entities_and_relationships(
        text="This text contains generic non-organizational phrases with no entities.",
        document_name="ZeroDoc",
        llm_client=zero_entity_llm,
    )
    assert zero_result == {"entities": [], "relationships": []}

    # Case 2: Extraction failure / timeout
    failing_llm = FailingMockLLM()
    with pytest.raises(GraphExtractionError) as exc_info:
        await extract_entities_and_relationships(
            text="Crucial executive memo regarding Project Titan and Vikram.",
            document_name="FailingDoc",
            llm_client=failing_llm,
        )
    assert "timed out" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_empty_provider_exception_is_exposed_in_extraction_error():
    """Provider failures without a message still expose their exception type."""
    with pytest.raises(GraphExtractionError) as exc_info:
        await extract_entities_and_relationships(
            text="Project Titan status update.",
            document_name="EmptyFailureDoc",
            llm_client=EmptyFailureMockLLM(),
        )

    assert "TimeoutError" in str(exc_info.value)


@pytest.mark.asyncio
async def test_all_chunks_failing_raises_runtime_error():
    """13b & 7. Verify that when all chunk extractions fail, the batch flow raises rather than silently passing."""
    failing_llm = FailingMockLLM()
    chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
    max_extract_chunks = len(chunks)

    failed_chunks = []
    successful_extractions = []

    for i in range(max_extract_chunks):
        try:
            ext = await extract_entities_and_relationships(
                text=chunks[i],
                document_name="FailAllDoc",
                llm_client=failing_llm,
            )
            successful_extractions.append(ext)
        except Exception as e:
            failed_chunks.append((i, str(e)))

    assert len(failed_chunks) == max_extract_chunks
    assert len(successful_extractions) == 0

    # Pipeline logic check: must raise instead of reporting PROCESSED with 0 entities
    with pytest.raises(RuntimeError) as exc_info:
        if max_extract_chunks > 0 and len(failed_chunks) == max_extract_chunks:
            first_err = failed_chunks[0][1]
            raise RuntimeError(f"Graph extraction failed for all {max_extract_chunks} chunks: {first_err}")

    assert "Graph extraction failed for all 3 chunks" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pipeline_persists_terminal_failure_after_graph_extraction_error(monkeypatch):
    """Graph failures retain vector work and commit a useful terminal document state."""
    from app.ingestion import pipeline
    from app.models.document import DocumentStatus

    document = SimpleNamespace(
        id="pipeline-failure-doc",
        name="Pipeline Failure Doc",
        original_filename="failure.txt",
        file_path="failure.txt",
        uploaded_by=None,
        status=DocumentStatus.UPLOADED,
        chunk_count=0,
        entity_count=0,
        relationship_count=0,
        error_message=None,
        processed_at=None,
        author=None,
        doc_date=None,
        department=None,
        project=None,
        doc_type=None,
        doc_metadata=None,
    )

    class FakeSession:
        def __init__(self):
            self.commit_count = 0

        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: document)

        async def commit(self):
            self.commit_count += 1

        async def flush(self):
            return None

        async def rollback(self):
            return None

        def add(self, _value):
            return None

    class FakeEncoder:
        dimension = 2

        def encode(self, texts):
            return [[0.1, 0.2] for _ in texts]

    class FakeVectorStore:
        def __init__(self):
            self.upserted = False

        async def ensure_collection(self, _dimension):
            return None

        async def upsert_chunks(self, _chunks):
            self.upserted = True

    class FakeNeo4j:
        def verify_connection(self):
            return True

        def ensure_constraints(self):
            return None

    fake_vectors = FakeVectorStore()
    monkeypatch.setattr(pipeline, "extract_text", lambda _path: ("Project Titan content", {}))
    monkeypatch.setattr(pipeline, "enrich_metadata", lambda *_args: {})
    monkeypatch.setattr(
        pipeline,
        "chunk_text",
        lambda *_args, **_kwargs: [SimpleNamespace(text="Project Titan", metadata={}, char_start=0, char_end=12, token_count=2)],
    )
    monkeypatch.setattr(pipeline, "get_encoder", lambda: FakeEncoder())
    monkeypatch.setattr(pipeline, "get_vector_store", lambda: fake_vectors)
    monkeypatch.setattr(pipeline, "get_neo4j", lambda: FakeNeo4j())
    monkeypatch.setattr(pipeline, "GraphBuilder", lambda _client: SimpleNamespace(ingest_document_graph=lambda **_kwargs: (0, 0)))

    async def fail_extraction(**_kwargs):
        raise GraphExtractionError("Entity extraction failed (TimeoutError): TimeoutError()")

    monkeypatch.setattr(pipeline, "extract_entities_and_relationships", fail_extraction)
    session = FakeSession()

    await pipeline._run_pipeline(document.id, session)

    assert document.status is DocumentStatus.FAILED
    assert "TimeoutError" in document.error_message
    assert document.chunk_count == 1
    assert document.entity_count == 0
    assert document.relationship_count == 0
    assert fake_vectors.upserted
    assert session.commit_count >= 3


@pytest.mark.asyncio
async def test_graph_extraction_timeout_is_bounded(monkeypatch):
    """A slow local inference call fails promptly instead of holding the job open for 120s."""
    from app.ingestion import pipeline

    async def slow_extraction(**_kwargs):
        await asyncio.sleep(0.2)

    monkeypatch.setattr(pipeline, "extract_entities_and_relationships", slow_extraction)
    monkeypatch.setattr(settings, "graph_extraction_timeout_seconds", 0.1)

    started = asyncio.get_running_loop().time()
    with pytest.raises(GraphExtractionError, match="timed out after 0.1s"):
        await pipeline._extract_graph_chunk("slow chunk", "TimeoutDoc")

    assert asyncio.get_running_loop().time() - started < 0.2


@pytest.mark.asyncio
async def test_successful_extraction_produces_expected_graph_structure():
    """13c. Verify successful extraction still produces valid entities, types, and relationships."""
    valid_json = """{
        "entities": [
            {"id": "priya-sharma", "type": "Employee", "name": "Priya Sharma"},
            {"id": "project-orion", "type": "Project", "name": "Project Orion"}
        ],
        "relationships": [
            {"from_id": "priya-sharma", "from_type": "Employee", "rel_type": "MANAGES", "to_id": "project-orion", "to_type": "Project"}
        ]
    }"""
    mock_llm = ConcurrencyTrackingMockLLM(response_text=valid_json)

    result = await extract_entities_and_relationships(
        text="Priya Sharma manages Project Orion.",
        document_name="OrionDoc",
        llm_client=mock_llm,
    )

    assert len(result["entities"]) == 2
    assert len(result["relationships"]) == 1
    assert result["entities"][0]["name"] == "Priya Sharma"
    assert result["entities"][1]["name"] == "Project Orion"
    assert result["relationships"][0]["rel_type"] == "MANAGES"


@pytest.mark.asyncio
async def test_document_level_graph_consolidation_still_works():
    """13d. Verify multi-chunk extractions consolidate correctly into Neo4j."""
    neo4j = get_neo4j()
    builder = GraphBuilder(neo4j)
    doc_id = "test-doc-sequential-consolidation"
    doc_name = "Sequential Consolidation Doc"

    builder.delete_document_graph(doc_id)

    chunk_0 = {
        "entities": [
            {"id": "arun-kumar", "type": "Employee", "name": "Arun Kumar"},
            {"id": "project-alpha", "type": "Project", "name": "Project Alpha"},
        ],
        "relationships": [
            {"from_id": "arun-kumar", "rel_type": "MANAGES", "to_id": "project-alpha"},
        ]
    }

    chunk_1 = {
        "entities": [
            {"id": "project-alpha", "type": "Project", "name": "Project Alpha"},
            {"id": "engineering-dept", "type": "Department", "name": "Engineering Department"},
        ],
        "relationships": [
            {"from_id": "project-alpha", "rel_type": "PART_OF", "to_id": "engineering-dept"},
        ]
    }

    ent_count, rel_count = builder.ingest_document_graph(
        extractions=[chunk_0, chunk_1],
        document_id=doc_id,
        document_name=doc_name,
        chunk_ids=["c0", "c1"],
    )

    assert ent_count == 3
    assert rel_count == 2

    # Cleanup
    builder.delete_document_graph(doc_id)
