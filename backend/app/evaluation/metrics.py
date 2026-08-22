"""
MemoraGraph – Evaluation Metrics

Calculates Precision@K, PathPrecision@K, AnswerRecall@K, intent classification accuracy,
and latency statistics. Supports 95% Bootstrap Confidence Intervals.
"""

import logging
import numpy as np
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


def calculate_precision_at_k(retrieved_ids: List[str], ground_truth_ids: List[str], k: int) -> float:
    """Calculate standard Precision@K."""
    if not retrieved_ids or not ground_truth_ids or k <= 0:
        return 0.0
    
    top_k_retrieved = retrieved_ids[:k]
    relevant_retrieved = sum(1 for rid in top_k_retrieved if rid in ground_truth_ids)
    return relevant_retrieved / k


def calculate_path_precision_at_k(retrieved_paths: List[str], ground_truth_paths: List[str], k: int) -> float:
    """
    Calculate Path Precision@K.
    Measures ratio of intent-allowed relationship types vs actual traversed types.
    """
    if not retrieved_paths or not ground_truth_paths or k <= 0:
        return 0.0
    
    top_k_paths = retrieved_paths[:k]
    matched_paths = sum(1 for path in top_k_paths if path in ground_truth_paths)
    return matched_paths / k


def calculate_answer_recall_at_k(generated_answer: str, ground_truth_answers: List[str]) -> float:
    """
    Evaluate AnswerRecall using keyword coverage of essential factual tokens.
    """
    if not generated_answer or not ground_truth_answers:
        return 0.0

    # Clean text to compare key facts
    import re
    def get_keywords(text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9-]{3,}\b", text.lower())
        # Filter stop words
        stops = {"the", "and", "for", "with", "that", "this", "from", "was", "were", "are", "project", "risk", "decision"}
        return {w for w in words if w not in stops}

    gen_keywords = get_keywords(generated_answer)
    best_recall = 0.0

    for gt in ground_truth_answers:
        gt_keywords = get_keywords(gt)
        if not gt_keywords:
            continue
        matches = len(gen_keywords.intersection(gt_keywords))
        recall = matches / len(gt_keywords)
        best_recall = max(best_recall, recall)

    return best_recall


def bootstrap_confidence_interval(
    data: List[float],
    num_bootstraps: int = 1000,
    confidence_level: float = 0.95,
) -> Tuple[float, float, float]:
    """
    Calculates bootstrap mean, standard deviation, and 95% Confidence Interval.
    """
    if not data:
        return 0.0, 0.0, (0.0, 0.0)
    
    arr = np.array(data)
    means = []
    
    for _ in range(num_bootstraps):
        sample = np.random.choice(arr, size=len(arr), replace=True)
        means.append(np.mean(sample))
        
    means = np.array(means)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    
    alpha = 1.0 - confidence_level
    lower_pct = (alpha / 2.0) * 100
    upper_pct = (1.0 - alpha / 2.0) * 100
    
    ci_lower = float(np.percentile(means, lower_pct))
    ci_upper = float(np.percentile(means, upper_pct))
    
    return mean_val, std_val, (ci_lower, ci_upper)
