"""Focused answer-generation regressions for source coherence and multi-part prompts."""

import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "backend")

from app.schemas.query import IntentResult
from app.retrieval.context_validator import extract_relevant_context


@pytest.mark.asyncio
async def test_answer_generation_keeps_dominant_document_and_calls_llm_once(monkeypatch):
    import app.llm.generator as generator_module

    query = "What caused the authentication incident, who resolved it, and what evidence confirms the resolution?"
    identity_chunks = [
        SimpleNamespace(document_id="identity", document_name="Document 01 Identity Service", chunk_id="c2", text="Resolution evidence and health checks.", score=0.81),
        SimpleNamespace(document_id="identity", document_name="Document 01 Identity Service", chunk_id="c1", text="Incorrect audience value. Arun Kumar corrected the audience configuration.", score=0.71),
        SimpleNamespace(document_id="identity", document_name="Document 01 Identity Service", chunk_id="c0", text="Shared authentication service context.", score=0.68),
        SimpleNamespace(document_id="unrelated", document_name="Security Incident Report", chunk_id="u0", text="Unrelated database incident.", score=0.67),
    ]
    calls = []

    class FakeLLM:
        async def complete(self, **kwargs):
            calls.append(kwargs)
            return "1. Cause: configuration correction. 2. Resolver: Daniel Joseph confirmed health checks. 3. Evidence: health checks passed."

    monkeypatch.setattr(
        generator_module,
        "get_hybrid_retriever",
        lambda: SimpleNamespace(_extract_seed_entity_candidates=lambda *_args: []),
    )
    monkeypatch.setattr(generator_module, "GraphRetriever", lambda: SimpleNamespace())
    monkeypatch.setattr(generator_module, "get_intent_classifier", lambda: SimpleNamespace(
        classify=lambda _query: IntentResult(
            intent="RISK_CAUSE",
            confidence=0.65,
            allowed_relationships=[],
        )
    ))
    monkeypatch.setattr(generator_module, "get_encoder", lambda: SimpleNamespace(encode_single=lambda _query: [0.1]))
    monkeypatch.setattr(generator_module, "get_vector_store", lambda: SimpleNamespace(search=lambda **_kwargs: _async_results(identity_chunks)))
    monkeypatch.setattr(generator_module, "get_llm_provider", lambda: FakeLLM())

    response = await generator_module.GroundedAnswerGenerator().generate_answer(query)

    assert len(calls) == 1
    assert {source.document_id for source in response.sources} == {"identity"}
    assert "Answer every distinct request explicitly" in calls[0]["user_message"]
    assert "Cause, Resolver, and" in calls[0]["user_message"]
    assert "do not combine unrelated sources" in calls[0]["user_message"]
    assert "FACT ROLE CHECK:" in calls[0]["user_message"]
    assert "CORRECTIVE ACTOR EVIDENCE" in calls[0]["user_message"]
    assert "incorrect audience" in response.answer.lower()
    assert "arun kumar" in response.answer.lower()


def test_relevant_context_preserves_cause_and_corrective_actor_lines():
    text = "\n".join([
        "Authentication incident overview.",
        "The investigation identified an incorrect audience value.",
        "Arun Kumar corrected the audience configuration.",
        "Daniel Joseph verified the service health checks.",
    ])

    context = extract_relevant_context(
        text,
        "What caused the authentication incident, who resolved it, and what evidence confirms the resolution?",
        max_chars=600,
    )

    assert "incorrect audience value" in context
    assert "Arun Kumar corrected" in context


async def _async_results(results):
    return results