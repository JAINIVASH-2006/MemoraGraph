"""
MemoraGraph – Evaluation Runner

Loads synthetic QA dataset, executes hybrid retrieval & generation pipeline,
calculates statistical distributions (means, standard deviations, bootstrap CIs)
for Precision@K, PathPrecision@K, Recall, Latency, and Intent classification.
"""

import json
import logging
import os
import time
from typing import List, Dict, Any

from app.llm.generator import get_answer_generator
from app.evaluation.metrics import (
    calculate_precision_at_k,
    calculate_path_precision_at_k,
    calculate_answer_recall_at_k,
    bootstrap_confidence_interval,
)

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Executes academic-style evaluations on MemoraGraph query pipeline."""

    def __init__(self, qa_dataset_path: str):
        self.dataset_path = qa_dataset_path
        if not os.path.exists(qa_dataset_path):
            raise FileNotFoundError(f"QA dataset not found at {qa_dataset_path}")
        
        with open(qa_dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)
            
        logger.info("Loaded evaluation dataset containing %d QA items.", len(self.dataset))

    async def run_evaluation(self, limit: int = 20) -> Dict[str, Any]:
        """
        Execute evaluation loop.
        
        Returns:
            Structured results report.
        """
        generator = get_answer_generator()
        items = self.dataset[:limit]

        precisions_at_1 = []
        precisions_at_5 = []
        path_precisions = []
        recalls = []
        intent_accuracies = []
        latencies = []

        logger.info("Running evaluation over %d samples...", len(items))

        for idx, item in enumerate(items, 1):
            query = item["query"]
            gt_doc_ids = item["ground_truth_document_ids"]
            gt_intent = item["ground_truth_intent"]
            gt_paths = item.get("ground_truth_paths", [])
            gt_answers = item.get("ground_truth_answers") or [item.get("answer") or ""]

            start_t = time.perf_counter()
            response = await generator.generate_answer(query, top_k=5)
            elapsed_ms = (time.perf_counter() - start_t) * 1000

            # 1. Standard Precision@K
            retrieved_doc_ids = [s.document_id for s in response.sources]
            p1 = calculate_precision_at_k(retrieved_doc_ids, gt_doc_ids, k=1)
            p5 = calculate_precision_at_k(retrieved_doc_ids, gt_doc_ids, k=5)
            precisions_at_1.append(p1)
            precisions_at_5.append(p5)

            # 2. Path Precision@K (allowed vs retrieved paths)
            retrieved_path_descs = [p.description for p in response.graph_paths if p.description]
            path_p = calculate_path_precision_at_k(retrieved_path_descs, gt_paths, k=5)
            path_precisions.append(path_p)

            # 3. Answer Recall
            recall = calculate_answer_recall_at_k(response.answer, gt_answers)
            recalls.append(recall)

            # 4. Intent classification accuracy
            intent_correct = 1.0 if response.intent == gt_intent else 0.0
            intent_accuracies.append(intent_correct)

            # 5. Latency
            latencies.append(elapsed_ms)

            logger.info(
                "Sample %d/%d: Query='%s' | Intent=%s (Correct: %s) | Latency=%.1fms | Recall=%.2f",
                idx, len(items), query[:30], response.intent, intent_correct == 1.0, elapsed_ms, recall
            )

        # Calculate Statistics with Bootstrap CIs
        metrics_report = {}
        metric_configs = {
            "Precision@1": precisions_at_1,
            "Precision@5": precisions_at_5,
            "PathPrecision@5": path_precisions,
            "AnswerRecall": recalls,
            "IntentAccuracy": intent_accuracies,
            "Latency_ms": latencies,
        }

        for name, data in metric_configs.items():
            mean, std, (ci_lower, ci_upper) = bootstrap_confidence_interval(data)
            metrics_report[name] = {
                "mean": round(mean, 4),
                "std": round(std, 4),
                "ci_95": (round(ci_lower, 4), round(ci_upper, 4)),
            }

        report = {
            "dataset_type": self.dataset[0].get("data_type", "SYNTHETIC_DEVELOPMENT_DATA"),
            "total_samples_evaluated": len(items),
            "metrics": metrics_report,
            "evaluation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Save to disk
        out_dir = "./data/evaluation"
        os.makedirs(out_dir, exist_ok=True)
        report_path = os.path.join(out_dir, "latest_evaluation_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info("Evaluation complete. Report saved to: %s", report_path)
        return report
