"""
MemoraGraph – CLI Evaluation Runner

Allows running evaluations over synthetic or custom Q&A datasets.
"""

import argparse
import asyncio
import logging
import sys
import os

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.embeddings.encoder import init_encoder
from app.embeddings.vector_store import init_vector_store
from app.graph.neo4j_client import init_neo4j
from app.llm.provider import init_llm_provider
from app.evaluation.runner import EvaluationRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("memoragraph-eval")


async def main():
    parser = argparse.ArgumentParser(description="MemoraGraph Academic Evaluation CLI")
    parser.add_argument(
        "--dataset",
        type=str,
        default="./data/evaluation/synthetic_qa.json",
        help="Path to evaluation QA dataset (JSON)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit number of test samples to run",
    )
    args = parser.parse_args()

    logger.info("Initializing system configurations for evaluation...")
    
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

    runner = EvaluationRunner(args.dataset)
    report = await runner.run_evaluation(limit=args.limit)

    print("\n==================================================")
    print("           MEMORAGRAPH EVALUATION REPORT           ")
    print("==================================================")
    print(f"Timestamp: {report['evaluation_timestamp']}")
    print(f"Dataset Type: {report['dataset_type']}")
    print(f"Total Samples Evaluated: {report['total_samples_evaluated']}")
    print("--------------------------------------------------")
    
    for metric_name, stats in report["metrics"].items():
        print(f"{metric_name:20} Mean: {stats['mean']:.4f}  | Std: {stats['std']:.4f} | 95% CI: [{stats['ci_95'][0]:.4f}, {stats['ci_95'][1]:.4f}]")
    print("==================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
