"""
MemoraGraph – Academic Evaluation Runner & Comparative Benchmark Harness

Supports:
1. Fast Retrieval Benchmark (No LLM):
   Fair three-way comparison on the exact same dataset & retrieval inputs:
   - Mode A: VECTOR_RAG (Qdrant vector retrieval only, zero Neo4j calls)
   - Mode B: STANDARD_GRAPHRAG (Vector retrieval + unrestricted/broad graph traversal, no intent routing)
   - Mode C: MEMORAGRAPH (Intent classification + directional intent-routed graph traversal + context validation)

2. Answer-Quality Validation Subset (LLM Generation):
   Separate, small 3-5 query validation measuring Answer F1, keyword recall,
   Ollama token counts, and generation latencies sequentially on Qwen3 4B.
"""

import json
import logging
import os
import time
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.embeddings.encoder import get_encoder
from app.embeddings.vector_store import get_vector_store
from app.retrieval.intent_classifier import get_intent_classifier
from app.retrieval.graph_retriever import GraphRetriever
from app.retrieval.hybrid_retriever import get_hybrid_retriever
from app.retrieval.context_validator import validate_evidence
from app.schemas.query import Source, GraphPath, IntentResult
from app.evaluation.metrics import (
    calculate_precision_at_k,
    calculate_document_recall_at_k,
    calculate_retrieval_f1_at_k,
    calculate_path_precision_at_k,
    calculate_answer_recall_at_k,
    calculate_answer_f1,
    bootstrap_confidence_interval,
)

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Executes academic-style retrieval and answer-quality evaluations on MemoraGraph."""

    def __init__(self, qa_dataset_path: str = "./data/evaluation/synthetic_qa.json"):
        self.dataset_path = qa_dataset_path
        if not os.path.exists(qa_dataset_path):
            raise FileNotFoundError(f"QA dataset not found at {qa_dataset_path}")

        with open(qa_dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)

        logger.info("Loaded evaluation dataset containing %d QA items from %s", len(self.dataset), qa_dataset_path)

    async def execute_mode_retrieval(
        self,
        query: str,
        strategy: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes mode-specific retrieval without calling the LLM.
        
        Fairness Guarantee:
        - All three modes retrieve from identical Qdrant collections with identical embeddings.
        - Vector RAG strictly never calls Neo4j.
        - Standard GraphRAG performs broad graph traversal with allowed_relationships=[] (no intent routing).
        - MemoraGraph performs intent-routed directional traversal using its natural intent classifier.
        - All three assemble evidence through the identical validate_evidence context pipeline.
        """
        start_total = time.perf_counter()
        encoder = get_encoder()
        vector_store = get_vector_store()
        hybrid_retriever = get_hybrid_retriever()
        graph_retriever = GraphRetriever()

        # 1. Intent Classification (MemoraGraph only)
        start_classify = time.perf_counter()
        classify_latency = 0.0
        predicted_intent = strategy.upper()
        intent_confidence = 1.0
        allowed_rels: List[str] = []

        if strategy == "memoragraph":
            classifier = get_intent_classifier()
            intent_res = classifier.classify(query)
            classify_latency = (time.perf_counter() - start_classify) * 1000
            predicted_intent = intent_res.intent
            intent_confidence = intent_res.confidence
            allowed_rels = [] if intent_res.low_confidence else intent_res.allowed_relationships
        elif strategy == "standard_graphrag":
            allowed_rels = []  # unrouted / broad traversal
        elif strategy == "vector_rag":
            allowed_rels = []  # not used

        # 2. Vector Search (identical for all modes)
        start_vec = time.perf_counter()
        query_emb = encoder.encode_single(query)
        vector_results = await vector_store.search(
            query_embedding=query_emb,
            top_k=top_k,
            filter_user_id=user_id,
        )
        vec_latency = (time.perf_counter() - start_vec) * 1000

        sources = [
            Source(
                document_id=r.document_id,
                document_name=r.document_name,
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                source_type="vector",
            )
            for r in vector_results
        ]

        # 3. Graph Traversal
        start_graph = time.perf_counter()
        graph_paths: List[GraphPath] = []
        graph_latency = 0.0

        if strategy != "vector_rag":
            seed_names = hybrid_retriever._extract_seed_entity_candidates(query, vector_results)
            if seed_names:
                graph_paths = graph_retriever.retrieve_paths(
                    seed_entity_names=seed_names,
                    allowed_relationships=allowed_rels,
                    max_hops=2,
                    user_id=user_id,
                )
            graph_latency = (time.perf_counter() - start_graph) * 1000

        # 4. Context Validation & Evidence Assembly (identical for all modes)
        start_val = time.perf_counter()
        is_fallback = (strategy == "memoragraph" and predicted_intent == "LOW_CONFIDENCE")
        evidence_dicts = validate_evidence(
            sources=sources,
            graph_paths=graph_paths,
            max_tokens=settings.max_context_tokens,
            query=query,
            is_fallback=is_fallback,
        )
        val_latency = (time.perf_counter() - start_val) * 1000
        total_retrieval_latency = (time.perf_counter() - start_total) * 1000

        # Build clean context representation
        doc_parts = []
        path_parts = []
        retrieved_chunk_ids = []
        retrieved_doc_ids = []

        for ev in evidence_dicts:
            if ev.get("path"):
                path_parts.append(f"GRAPH PATH:\n{ev['text']}")
            else:
                doc_parts.append(f"SOURCE: {ev['source_document_id']} | CHUNK: {ev.get('chunk_id', '')}\n{ev['text']}")
                if ev["source_document_id"] not in retrieved_doc_ids:
                    retrieved_doc_ids.append(ev["source_document_id"])
                if ev.get("chunk_id") and ev["chunk_id"] not in retrieved_chunk_ids:
                    retrieved_chunk_ids.append(ev["chunk_id"])

        # Also preserve original retrieved top_k source IDs
        for s in sources:
            if s.document_id not in retrieved_doc_ids:
                retrieved_doc_ids.append(s.document_id)
            if s.chunk_id and s.chunk_id not in retrieved_chunk_ids:
                retrieved_chunk_ids.append(s.chunk_id)

        context_text = "=== DOCUMENT EVIDENCE ===\n" + ("\n\n".join(doc_parts) if doc_parts else "None")
        if path_parts:
            context_text += "\n\n=== KNOWLEDGE GRAPH RELATIONSHIPS ===\n" + "\n\n".join(path_parts)

        context_chars = len(context_text)
        estimated_context_tokens = max(1, context_chars // 4)

        # Graph node & edge metrics
        unique_nodes = {n.id for p in graph_paths for n in p.nodes}
        nodes_count = len(unique_nodes)
        edges_count = sum(len(p.edges) for p in graph_paths)
        rel_types = sorted(list({e.type for p in graph_paths for e in p.edges}))
        path_descs = [p.description for p in graph_paths if p.description]

        return {
            "strategy": strategy,
            "predicted_intent": predicted_intent,
            "intent_confidence": round(intent_confidence, 4),
            "retrieved_doc_ids": retrieved_doc_ids,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "graph_paths": graph_paths,
            "path_descriptions": path_descs,
            "graph_nodes_retrieved": nodes_count,
            "graph_edges_traversed": edges_count,
            "retrieved_relationship_types": rel_types,
            "context_chars": context_chars,
            "estimated_context_tokens": estimated_context_tokens,
            "vector_latency_ms": round(vec_latency, 2),
            "graph_latency_ms": round(graph_latency, 2),
            "classify_latency_ms": round(classify_latency, 2),
            "validation_latency_ms": round(val_latency, 2),
            "retrieval_latency_ms": round(total_retrieval_latency, 2),
        }

    async def evaluate_retrieval_strategy(
        self,
        strategy: str = "memoragraph",
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a single retrieval strategy sequentially across benchmark queries without calling LLM.
        """
        items = self.dataset[:limit] if limit else self.dataset

        precisions_at_1 = []
        precisions_at_5 = []
        recalls_at_5 = []
        f1_scores_at_5 = []
        path_precisions_at_5 = []
        intent_accuracies = []
        graph_nodes_list = []
        graph_edges_list = []
        context_chars_list = []
        estimated_tokens_list = []
        vector_latencies = []
        graph_latencies = []
        total_latencies = []

        per_query_details = []

        logger.info(
            "Executing retrieval benchmark for '%s' over %d queries (Zero LLM calls)...",
            strategy.upper(), len(items)
        )

        for idx, item in enumerate(items, 1):
            query = item["query"]
            gt_doc_ids = item.get("ground_truth_document_ids", [])
            gt_intent = item.get("intent") or item.get("ground_truth_intent", "")
            gt_paths = item.get("ground_truth_paths", [])

            ret_res = await self.execute_mode_retrieval(
                query=query,
                strategy=strategy,
                top_k=5,
            )

            # Retrieval Quality Metrics
            p1 = calculate_precision_at_k(ret_res["retrieved_doc_ids"], gt_doc_ids, k=1)
            p5 = calculate_precision_at_k(ret_res["retrieved_doc_ids"], gt_doc_ids, k=5)
            r5 = calculate_document_recall_at_k(ret_res["retrieved_doc_ids"], gt_doc_ids, k=5)
            f1_5 = calculate_retrieval_f1_at_k(p5, r5)
            path_p = calculate_path_precision_at_k(ret_res["path_descriptions"], gt_paths, k=5)

            intent_correct = 1.0 if ret_res["predicted_intent"] == gt_intent else 0.0

            precisions_at_1.append(p1)
            precisions_at_5.append(p5)
            recalls_at_5.append(r5)
            f1_scores_at_5.append(f1_5)
            path_precisions_at_5.append(path_p)
            intent_accuracies.append(intent_correct)
            graph_nodes_list.append(float(ret_res["graph_nodes_retrieved"]))
            graph_edges_list.append(float(ret_res["graph_edges_traversed"]))
            context_chars_list.append(float(ret_res["context_chars"]))
            estimated_tokens_list.append(float(ret_res["estimated_context_tokens"]))
            vector_latencies.append(ret_res["vector_latency_ms"])
            graph_latencies.append(ret_res["graph_latency_ms"])
            total_latencies.append(ret_res["retrieval_latency_ms"])

            relevant_retrieved = [did for did in set(ret_res["retrieved_doc_ids"]) if did in gt_doc_ids]

            per_query_details.append({
                "query_id": item.get("id", f"q{idx:03d}"),
                "query": query,
                "mode": strategy,
                "expected_intent": gt_intent,
                "predicted_intent": ret_res["predicted_intent"],
                "intent_confidence": ret_res["intent_confidence"],
                "precision_at_1": round(p1, 4),
                "precision_at_5": round(p5, 4),
                "recall_at_5": round(r5, 4),
                "f1_at_5": round(f1_5, 4),
                "path_precision_at_5": round(path_p, 4),
                "relevant_documents_retrieved": relevant_retrieved,
                "retrieved_chunk_ids": ret_res["retrieved_chunk_ids"],
                "graph_nodes_retrieved": ret_res["graph_nodes_retrieved"],
                "graph_edges_traversed": ret_res["graph_edges_traversed"],
                "retrieved_relationship_types": ret_res["retrieved_relationship_types"],
                "context_size_chars": ret_res["context_chars"],
                "estimated_context_tokens": ret_res["estimated_context_tokens"],
                "retrieval_latency_ms": ret_res["retrieval_latency_ms"],
            })

            logger.info(
                "[%s] %d/%d: Query='%s' | P@5=%.2f | R@5=%.2f | F1@5=%.2f | Nodes=%d | Latency=%.1fms",
                strategy.upper(), idx, len(items), query[:30], p5, r5, f1_5,
                ret_res["graph_nodes_retrieved"], ret_res["retrieval_latency_ms"]
            )

        # Statistical aggregation with bootstrap CIs
        metric_configs = {
            "Precision@1": precisions_at_1,
            "Precision@5": precisions_at_5,
            "Recall@5": recalls_at_5,
            "F1@5": f1_scores_at_5,
            "PathPrecision@5": path_precisions_at_5,
            "IntentAccuracy": intent_accuracies,
            "GraphNodesRetrieved": graph_nodes_list,
            "GraphEdgesTraversed": graph_edges_list,
            "ContextSizeChars": context_chars_list,
            "EstimatedContextTokens": estimated_tokens_list,
            "VectorRetrievalLatency_ms": vector_latencies,
            "GraphRetrievalLatency_ms": graph_latencies,
            "TotalRetrievalLatency_ms": total_latencies,
        }

        metrics_report = {}
        for name, data in metric_configs.items():
            mean, std, (ci_lower, ci_upper) = bootstrap_confidence_interval(data)
            metrics_report[name] = {
                "mean": round(mean, 4),
                "std": round(std, 4),
                "ci_95": (round(ci_lower, 4), round(ci_upper, 4)),
            }

        return {
            "strategy": strategy,
            "total_samples": len(items),
            "metrics": metrics_report,
            "details": per_query_details,
        }

    async def run_comparative_retrieval_benchmark(
        self,
        limit: Optional[int] = None,
        strategies: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Runs the fair three-way comparative retrieval benchmark sequentially across all queries.
        Generates latest_evaluation_report.json, comparative_results.json, and comparative_results.md.
        Zero LLM calls are made.
        """
        if strategies is None:
            strategies = ["vector_rag", "standard_graphrag", "memoragraph"]

        results = {}
        out_dir = "./data/evaluation"
        os.makedirs(out_dir, exist_ok=True)

        for strat in strategies:
            logger.info("==================================================")
            logger.info("STARTING RETRIEVAL BENCHMARK: %s", strat.upper())
            logger.info("==================================================")
            results[strat] = await self.evaluate_retrieval_strategy(strategy=strat, limit=limit)

        comparative_report = {
            "benchmark_type": "THREE_WAY_RETRIEVAL_BENCHMARK",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dataset_path": self.dataset_path,
            "total_queries_per_strategy": len(self.dataset[:limit] if limit else self.dataset),
            "strategies": strategies,
            "comparative_metrics": {strat: results[strat]["metrics"] for strat in strategies},
            "detailed_results": results,
        }

        # 1. Output latest_evaluation_report.json (MemoraGraph retrieval metrics)
        latest_report = {
            "dataset_type": "BENCHMARK_SYNTHETIC_QA",
            "benchmark_type": "RETRIEVAL_EVALUATION",
            "mode": "memoragraph",
            "total_samples_evaluated": comparative_report["total_queries_per_strategy"],
            "metrics": results.get("memoragraph", results[strategies[0]])["metrics"],
            "evaluation_timestamp": comparative_report["timestamp"],
        }
        latest_path = os.path.join(out_dir, "latest_evaluation_report.json")
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(latest_report, f, indent=2)

        # 2. Output comparative_results.json
        comp_json_path = os.path.join(out_dir, "comparative_results.json")
        with open(comp_json_path, "w", encoding="utf-8") as f:
            json.dump(comparative_report, f, indent=2)

        # 3. Output comparative_results.md
        md_content = self._generate_markdown_report(comparative_report)
        comp_md_path = os.path.join(out_dir, "comparative_results.md")
        with open(comp_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info("Comparative retrieval evaluation complete! Reports saved to %s", out_dir)
        return comparative_report

    async def run_answer_quality_benchmark(
        self,
        sample_ids: Optional[List[str]] = None,
        limit: int = 4,
    ) -> Dict[str, Any]:
        """
        Executes the separate, small answer-quality validation subset on 3-5 representative queries.
        Invokes Qwen3 4B via GroundedAnswerGenerator sequentially across all three modes.
        Saves output exclusively to data/evaluation/answer_quality_results.json.
        """
        from app.llm.generator import get_answer_generator

        generator = get_answer_generator()
        out_dir = "./data/evaluation"
        os.makedirs(out_dir, exist_ok=True)

        # Select 3-5 representative queries
        if sample_ids:
            subset = [item for item in self.dataset if item.get("id") in sample_ids]
        else:
            subset = self.dataset[:limit]

        strategies = ["vector_rag", "standard_graphrag", "memoragraph"]
        quality_results = {
            "benchmark_type": "ANSWER_QUALITY_VALIDATION_SUBSET",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "llm_model": settings.llm_model,
            "total_queries": len(subset),
            "evaluated_query_ids": [item["id"] for item in subset],
            "mode_aggregates": {},
            "query_evaluations": [],
        }

        logger.info("Starting answer-quality evaluation for %d queries on %s...", len(subset), settings.llm_model)

        mode_stats = {s: {"recalls": [], "f1s": [], "p_toks": [], "c_toks": [], "latencies": []} for s in strategies}

        for item in subset:
            q_id = item["id"]
            query = item["query"]
            gt_answers = item.get("ground_truth_answers") or [item.get("ground_truth_answer", "")]

            q_eval = {
                "id": q_id,
                "query": query,
                "intent": item.get("intent", ""),
                "ground_truth_answer": item.get("ground_truth_answer", ""),
                "modes": {},
            }

            for mode in strategies:
                logger.info("Evaluating Answer Quality [%s] for %s: '%s'", mode, q_id, query[:30])
                res = await generator.generate_answer(
                    query=query,
                    top_k=5,
                    retrieval_strategy=mode,
                )

                rec = calculate_answer_recall_at_k(res.answer, gt_answers)
                f1 = calculate_answer_f1(res.answer, gt_answers)
                p_tok = res.retrieval_metadata.prompt_tokens or 0
                c_tok = res.retrieval_metadata.completion_tokens or 0
                g_lat = res.retrieval_metadata.generation_time_ms
                t_lat = res.retrieval_metadata.total_time_ms

                mode_stats[mode]["recalls"].append(rec)
                mode_stats[mode]["f1s"].append(f1)
                mode_stats[mode]["p_toks"].append(p_tok)
                mode_stats[mode]["c_toks"].append(c_tok)
                mode_stats[mode]["latencies"].append(t_lat)

                q_eval["modes"][mode] = {
                    "answer": res.answer,
                    "answer_recall": round(rec, 4),
                    "answer_f1": round(f1, 4),
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "generation_latency_ms": round(g_lat, 2),
                    "total_latency_ms": round(t_lat, 2),
                }

            quality_results["query_evaluations"].append(q_eval)

        # Compute summary averages
        for mode in strategies:
            st = mode_stats[mode]
            n = len(st["recalls"]) or 1
            quality_results["mode_aggregates"][mode] = {
                "mean_answer_recall": round(sum(st["recalls"]) / n, 4),
                "mean_answer_f1": round(sum(st["f1s"]) / n, 4),
                "mean_prompt_tokens": round(sum(st["p_toks"]) / n, 2),
                "mean_completion_tokens": round(sum(st["c_toks"]) / n, 2),
                "mean_total_latency_ms": round(sum(st["latencies"]) / n, 2),
            }

        # Save answer_quality_results.json
        aq_path = os.path.join(out_dir, "answer_quality_results.json")
        with open(aq_path, "w", encoding="utf-8") as f:
            json.dump(quality_results, f, indent=2)

        logger.info("Answer-quality validation complete! Saved to %s", aq_path)
        return quality_results

    def _generate_markdown_report(self, report: Dict[str, Any]) -> str:
        metrics = report["comparative_metrics"]

        lines = [
            "# MemoraGraph: Academic Comparative Retrieval Benchmark Report",
            "",
            f"**Benchmark Type:** Pure Retrieval & Evidence Assembly (Zero LLM Generation)  ",
            f"**Timestamp:** {report['timestamp']}  ",
            f"**Total Queries Evaluated per Strategy:** {report['total_queries_per_strategy']}  ",
            "",
            "## 1. Executive Summary & Retrieval Comparison Table",
            "",
            "| Metric | Baseline RAG (Vector Only) | Standard GraphRAG (Unrouted) | MemoraGraph (Intent-Routed) |",
            "| :--- | :---: | :---: | :---: |",
        ]

        metric_names = [
            ("Precision@1", "Precision@1"),
            ("Precision@5", "Precision@5"),
            ("Recall@5", "Recall@5"),
            ("F1@5", "Retrieval F1@5"),
            ("PathPrecision@5", "Path Precision@5"),
            ("IntentAccuracy", "Intent Accuracy"),
            ("GraphNodesRetrieved", "Avg Graph Nodes Retrieved"),
            ("GraphEdgesTraversed", "Avg Graph Edges Traversed"),
            ("ContextSizeChars", "Avg Context Size (Chars)"),
            ("EstimatedContextTokens", "Avg Estimated Context Tokens"),
            ("VectorRetrievalLatency_ms", "Vector Latency (ms)"),
            ("GraphRetrievalLatency_ms", "Graph Latency (ms)"),
            ("TotalRetrievalLatency_ms", "Total Retrieval Latency (ms)"),
        ]

        for m_key, m_label in metric_names:
            v_val = metrics.get("vector_rag", {}).get(m_key, {}).get("mean", 0.0)
            s_val = metrics.get("standard_graphrag", {}).get(m_key, {}).get("mean", 0.0)
            m_val = metrics.get("memoragraph", {}).get(m_key, {}).get("mean", 0.0)
            lines.append(f"| **{m_label}** | {v_val:.4f} | {s_val:.4f} | **{m_val:.4f}** |")

        lines.extend([
            "",
            "## 2. 95% Bootstrap Confidence Intervals",
            "",
            "| Metric | Baseline RAG (Vector) 95% CI | Standard GraphRAG 95% CI | MemoraGraph 95% CI |",
            "| :--- | :---: | :---: | :---: |",
        ])

        for m_key, m_label in metric_names:
            v_ci = metrics.get("vector_rag", {}).get(m_key, {}).get("ci_95", (0.0, 0.0))
            s_ci = metrics.get("standard_graphrag", {}).get(m_key, {}).get("ci_95", (0.0, 0.0))
            m_ci = metrics.get("memoragraph", {}).get(m_key, {}).get("ci_95", (0.0, 0.0))
            lines.append(f"| **{m_label}** | [{v_ci[0]:.4f}, {v_ci[1]:.4f}] | [{s_ci[0]:.4f}, {s_ci[1]:.4f}] | **[{m_ci[0]:.4f}, {m_ci[1]:.4f}]** |")

        lines.extend([
            "",
            "## 3. Research Analysis & Methodological Insights",
            "",
            "- **Graph Noise Reduction:** Comparing unrouted graph traversal against intent-routed directional traversal quantifies how many irrelevant graph edges and nodes are pruned.",
            "- **Context & Token Economy:** Shows how intent-routed retrieval prevents prompt bloating and keeps context tight without sacrificing relevant relations.",
            "- **Retrieval Latency:** Isolates vector and graph traversal latency from expensive LLM inference, ensuring an objective comparison of retrieval mechanics.",
        ])

        return "\n".join(lines)

    # Backwards compatibility method aliases
    run_comparative_evaluation = run_comparative_retrieval_benchmark
    evaluate_strategy = evaluate_retrieval_strategy
    run_evaluation = run_comparative_retrieval_benchmark


# Backwards compatibility module helper
async def run_evaluation(limit: Optional[int] = None) -> Dict[str, Any]:
    runner = EvaluationRunner("./data/evaluation/synthetic_qa.json")
    return await runner.run_comparative_retrieval_benchmark(limit=limit)

