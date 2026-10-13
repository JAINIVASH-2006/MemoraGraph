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


def calculate_document_recall_at_k(retrieved_ids: List[str], ground_truth_ids: List[str], k: int) -> float:
    """Calculate Document Recall@K: ratio of relevant documents retrieved among all relevant documents."""
    if not retrieved_ids or not ground_truth_ids or k <= 0:
        return 0.0
    top_k_retrieved = set(retrieved_ids[:k])
    relevant_retrieved = sum(1 for gtid in set(ground_truth_ids) if gtid in top_k_retrieved)
    return relevant_retrieved / len(set(ground_truth_ids))


def calculate_f1_score(precision: float, recall: float) -> float:
    """Calculate standard F1 harmonic mean: 2 * P * R / (P + R). Handles zero-division safely."""
    if (precision + recall) <= 0.0:
        return 0.0
    return (2.0 * precision * recall) / (precision + recall)


def calculate_retrieval_f1_at_k(precision: float, recall: float) -> float:
    """Alias for calculate_f1_score for retrieval metrics."""
    return calculate_f1_score(precision, recall)


def calculate_path_precision_at_k(retrieved_paths: List[str], ground_truth_paths: List[str], k: int) -> float:
    """
    Calculate Path Precision@K.
    Measures ratio of intent-allowed relationship types vs actual traversed types.
    Matches either exact string representation or semantic relationship/entity containment.
    """
    if not retrieved_paths or not ground_truth_paths or k <= 0:
        return 0.0
    
    top_k_paths = retrieved_paths[:k]
    
    def matches_ground_truth(path: str) -> bool:
        if path in ground_truth_paths:
            return True
        p_lower = path.lower()
        for gt in ground_truth_paths:
            gt_lower = gt.lower()
            if gt_lower in p_lower or p_lower in gt_lower:
                return True
            import re
            gt_words = [w for w in re.findall(r"\b[a-zA-Z0-9_-]+\b", gt_lower) if w not in ("project", "the", "a", "an")]
            if gt_words and all(w in p_lower for w in gt_words):
                return True
        return False

    matched_paths = sum(1 for path in top_k_paths if matches_ground_truth(path))
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


def calculate_answer_f1(generated_answer: str, ground_truth_answers: List[str]) -> float:
    """
    Evaluate Answer F1 score using harmonic mean of keyword precision and keyword recall.
    """
    if not generated_answer or not ground_truth_answers:
        return 0.0

    import re
    def get_keywords(text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9-]{3,}\b", text.lower())
        stops = {"the", "and", "for", "with", "that", "this", "from", "was", "were", "are", "project", "risk", "decision"}
        return {w for w in words if w not in stops}

    gen_keywords = get_keywords(generated_answer)
    if not gen_keywords:
        return 0.0

    best_f1 = 0.0
    for gt in ground_truth_answers:
        gt_keywords = get_keywords(gt)
        if not gt_keywords:
            continue
        matches = len(gen_keywords.intersection(gt_keywords))
        prec = matches / len(gen_keywords)
        rec = matches / len(gt_keywords)
        f1 = calculate_f1_score(prec, rec)
        best_f1 = max(best_f1, f1)

    return best_f1


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
