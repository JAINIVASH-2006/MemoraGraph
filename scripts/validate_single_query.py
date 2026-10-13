import asyncio
import json
import logging
from app.config import settings
from app.embeddings.encoder import init_encoder
from app.embeddings.vector_store import init_vector_store
from app.graph.neo4j_client import init_neo4j
from app.llm.provider import init_llm_provider
from app.llm.generator import get_answer_generator
from app.evaluation.runner import EvaluationRunner

logging.basicConfig(level=logging.INFO)

# Init singletons
init_encoder(settings.embedding_model)
init_vector_store(
    url=settings.qdrant_url,
    api_key=settings.qdrant_api_key,
    collection=settings.qdrant_collection,
)
init_neo4j(
    uri=settings.neo4j_uri,
    username=settings.neo4j_username,
    password=settings.neo4j_password,
)
init_llm_provider(
    provider=settings.llm_provider,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
)

runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
print(f"Total queries loaded: {len(runner.dataset)}")

# Check ground truth coverage
missing_gt = []
for item in runner.dataset:
    if not item.get("ground_truth_answer") or not item.get("ground_truth_entities"):
        missing_gt.append(item.get("id"))
print(f"Queries with missing ground truth: {len(missing_gt)} (ids: {missing_gt})")

sample = runner.dataset[0]
print(f"Sample query: {sample['id']} - {sample['query']} (Intent: {sample['intent']})")
print(f"Ground truth entities: {sample.get('ground_truth_entities')}")
print(f"Ground truth answer: {sample.get('ground_truth_answer')}")

generator = get_answer_generator()

async def test_modes():
    results = {}
    for mode in ["vector_rag", "standard_graphrag", "memoragraph"]:
        print(f"\n==========================================")
        print(f"Testing Mode: {mode}")
        print(f"==========================================")
        res = await generator.generate_answer(sample["query"], retrieval_strategy=mode)
        results[mode] = res
        print(f"Mode: {mode}")
        print(f"Answer: {res.answer[:150]}...")
        print(f"Graph paths retrieved: {len(res.graph_paths)}")
        print(f"Sources retrieved: {len(res.sources)}")
        print(f"Prompt tokens: {res.retrieval_metadata.prompt_tokens}")
        print(f"Completion tokens: {res.retrieval_metadata.completion_tokens}")
        print(f"Retrieval latency: {res.retrieval_metadata.retrieval_time_ms} ms")
        print(f"Generation latency: {res.retrieval_metadata.generation_time_ms} ms")
        print(f"Total latency: {res.retrieval_metadata.total_time_ms} ms")
        if res.graph_paths:
            print(f"Sample graph path: {res.graph_paths[0].description}")

    print("\n==========================================")
    print("VERIFICATION SUMMARY")
    print("==========================================")
    v_paths = len(results["vector_rag"].graph_paths)
    s_paths = len(results["standard_graphrag"].graph_paths)
    m_paths = len(results["memoragraph"].graph_paths)
    print(f"Vector RAG graph paths: {v_paths} (Expected: 0)")
    print(f"Standard GraphRAG graph paths: {s_paths} (Expected: > 0 unrouted)")
    print(f"MemoraGraph graph paths: {m_paths} (Expected: > 0 intent-routed)")
    assert v_paths == 0, "Vector RAG should not retrieve graph paths"
    print("All strategy assertions PASSED!")

if __name__ == "__main__":
    asyncio.run(test_modes())
