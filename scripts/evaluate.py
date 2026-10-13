"""
MemoraGraph – Academic Evaluation CLI

Usage:
1. Fast Retrieval Benchmark (No LLM, evaluates all 26 queries across all 3 modes):
   python scripts/evaluate.py --mode retrieval --strategy all

2. Small Answer-Quality Validation Subset (LLM generation on 3-5 representative queries):
   python scripts/evaluate.py --mode answer_quality --limit 4
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
        "--mode",
        type=str,
        default="retrieval",
        choices=["retrieval", "answer_quality"],
        help="Benchmark mode: 'retrieval' (fast retrieval evaluation, zero LLM calls) or 'answer_quality' (small 3-5 query LLM validation)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="all",
        choices=["all", "vector_rag", "standard_graphrag", "memoragraph"],
        help="Strategy to evaluate in retrieval mode: 'all' (3-way comparative benchmark) or a specific strategy",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of test samples to run (default: all queries for retrieval, 4 for answer_quality)",
    )
    args = parser.parse_args()

    logger.info("Initializing system singletons for evaluation...")
    
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

    runner = EvaluationRunner(args.dataset)

    if args.mode == "retrieval":
        if args.strategy == "all":
            if hasattr(runner, "run_comparative_retrieval_benchmark"):
                report = await runner.run_comparative_retrieval_benchmark(limit=args.limit)
            elif hasattr(runner, "run_comparative_evaluation"):
                report = await runner.run_comparative_evaluation(limit=args.limit)
            else:
                raise AttributeError("EvaluationRunner object has no attribute 'run_comparative_retrieval_benchmark'")
            print("\n==================================================")
            print("  MEMORAGRAPH THREE-WAY RETRIEVAL BENCHMARK DONE  ")
            print("==================================================")
            print(f"Timestamp: {report['timestamp']}")
            print(f"Total Queries Evaluated per Mode: {report['total_queries_per_strategy']}")
            print(f"Comparative report saved to: ./data/evaluation/comparative_results.md")
            print(f"Comparative JSON saved to:   ./data/evaluation/comparative_results.json")
            print(f"Latest report saved to:       ./data/evaluation/latest_evaluation_report.json")
            print("==================================================\n")
        else:
            if hasattr(runner, "evaluate_retrieval_strategy"):
                res = await runner.evaluate_retrieval_strategy(strategy=args.strategy, limit=args.limit)
            elif hasattr(runner, "evaluate_strategy"):
                res = await runner.evaluate_strategy(strategy=args.strategy, limit=args.limit)
            else:
                raise AttributeError("EvaluationRunner object has no attribute 'evaluate_retrieval_strategy'")
            print("\n==================================================")
            print(f"   RETRIEVAL EVALUATION REPORT: {args.strategy.upper()}   ")
            print("==================================================")
            print(f"Total Queries Evaluated: {res['total_samples']}")
            print("--------------------------------------------------")
            for metric_name, stats in res["metrics"].items():
                print(f"{metric_name:25} Mean: {stats['mean']:.4f}  | Std: {stats['std']:.4f} | 95% CI: [{stats['ci_95'][0]:.4f}, {stats['ci_95'][1]:.4f}]")
            print("==================================================\n")

    elif args.mode == "answer_quality":
        # Only initialize LLM provider for the answer-quality subset
        init_llm_provider(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
        limit_val = args.limit if args.limit is not None else 4
        if hasattr(runner, "run_answer_quality_benchmark"):
            res = await runner.run_answer_quality_benchmark(limit=limit_val)
        elif hasattr(runner, "run_comparative_evaluation"):
            res = await runner.run_comparative_evaluation(limit=limit_val)
        else:
            raise AttributeError("EvaluationRunner object has no attribute 'run_answer_quality_benchmark'")
        print("\n==================================================")
        print("  MEMORAGRAPH ANSWER-QUALITY VALIDATION SUBSET DONE ")
        print("==================================================")
        print(f"Timestamp: {res['timestamp']}")
        print(f"Total Queries Evaluated: {res['total_queries']}")
        print(f"Results saved to: ./data/evaluation/answer_quality_results.json")
        print("--------------------------------------------------")
        for mode, agg in res["mode_aggregates"].items():
            print(f"Mode [{mode:18}] AnsRecall: {agg['mean_answer_recall']:.4f} | AnsF1: {agg['mean_answer_f1']:.4f} | Latency: {agg['mean_total_latency_ms']:.1f}ms")
        print("==================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
