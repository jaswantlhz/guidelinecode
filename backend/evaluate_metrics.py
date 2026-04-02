"""
evaluate_metrics.py — Comprehensive RAG Evaluation for CPIC Pharmacogenomics System
=====================================================================================

Metrics Evaluated
-----------------
RETRIEVAL METRICS:
  • Precision@K          — Fraction of retrieved docs that are relevant
  • Recall@K             — Fraction of relevant docs that were retrieved
  • F1@K                 — Harmonic mean of Precision + Recall
  • MRR                  — Mean Reciprocal Rank (how soon the first relevant doc appears)
  • MAP                  — Mean Average Precision (area under precision-recall curve)
  • NDCG@K               — Normalized Discounted Cumulative Gain (rank-weighted relevance)
  • Hit Rate@K           — Whether at least one relevant doc appeared in top-K

GENERATION METRICS (RAGAS-proxy):
  • Context Precision    — Average reranker score of top-K sources
  • Faithfulness         — Fraction of answer tokens grounded in retrieved context
  • Answer Relevancy     — Answer density proxy via logistic of (answer_len / context_len)

Usage
-----
  # Run with built-in test suite (no external LLM calls — uses offline retrieval only):
  cd backend
  python evaluate_metrics.py

  # Run end-to-end including LLM generation (requires OPENROUTER_API_KEY in agent/.env):
  python evaluate_metrics.py --full-rag

  # Save results to JSON:
  python evaluate_metrics.py --output results/eval_results.json

  # Verbose chunk output:
  python evaluate_metrics.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Add backend to sys.path so imports work when run from project root ──
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluate_metrics")


# ══════════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvalQuery:
    """A single evaluation query with annotated relevant document IDs."""
    query_id: str
    gene: str
    drug: str
    question: str
    # Known relevant chunk keywords/phrases (used for soft relevance matching when no IDs)
    relevant_keywords: List[str] = field(default_factory=list)
    # Expected answer keywords present if the answer is correct
    expected_answer_keywords: List[str] = field(default_factory=list)
    # Ground truth: list of relevant doc title fragments
    relevant_titles: List[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """Results for a single query's retrieval step."""
    query_id: str
    retrieved_docs: List[Dict]          # [{title, score, text, relevant: bool}]
    relevant_count: int                 # |R| — total known relevant docs
    precision_at_k: Dict[int, float]    # {1: 0.0, 3: 0.33, 5: 0.6, ...}
    recall_at_k: Dict[int, float]
    f1_at_k: Dict[int, float]
    average_precision: float            # AP for MAP computation
    reciprocal_rank: float              # For MRR computation
    ndcg_at_k: Dict[int, float]
    hit_rate_at_k: Dict[int, float]


@dataclass
class GenerationResult:
    """Results for a single query's generation (RAG) step."""
    query_id: str
    answer: str
    answer_word_count: int
    context_precision: float
    faithfulness: float
    answer_relevancy: float
    source_count: int
    latency_seconds: float
    expected_keywords_found: List[str]
    expected_keywords_missing: List[str]
    keyword_hit_rate: float


@dataclass
class AggregateMetrics:
    """Aggregate across all queries."""
    total_queries: int = 0
    # Retrieval
    mean_precision: Dict[int, float] = field(default_factory=dict)
    mean_recall: Dict[int, float] = field(default_factory=dict)
    mean_f1: Dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    map_score: float = 0.0
    mean_ndcg: Dict[int, float] = field(default_factory=dict)
    mean_hit_rate: Dict[int, float] = field(default_factory=dict)
    # Generation
    mean_context_precision: float = 0.0
    mean_faithfulness: float = 0.0
    mean_answer_relevancy: float = 0.0
    mean_latency_seconds: float = 0.0
    mean_keyword_hit_rate: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Test corpus — CPIC pharmacogenomics evaluation queries
# ══════════════════════════════════════════════════════════════════════════════

EVAL_QUERIES: List[EvalQuery] = [
    EvalQuery(
        query_id="Q1",
        gene="CYP2D6",
        drug="codeine",
        question="What is the recommended codeine dose for a CYP2D6 poor metabolizer?",
        relevant_keywords=["poor metabolizer", "codeine", "CYP2D6", "ultrarapid", "dose", "avoid"],
        expected_answer_keywords=["poor metabolizer", "avoid", "alternative"],
        relevant_titles=["cpic", "codeine", "CYP2D6"],
    ),
    EvalQuery(
        query_id="Q2",
        gene="CYP2D6",
        drug="codeine",
        question="What are the activity scores for CYP2D6 alleles?",
        relevant_keywords=["activity score", "allele", "CYP2D6", "phenotype", "diplotype"],
        expected_answer_keywords=["activity score", "allele"],
        relevant_titles=["cpic", "CYP2D6"],
    ),
    EvalQuery(
        query_id="Q3",
        gene="CYP2C19",
        drug="clopidogrel",
        question="How does CYP2C19 poor metabolizer status affect clopidogrel efficacy?",
        relevant_keywords=["CYP2C19", "clopidogrel", "poor metabolizer", "platelet", "antiplatelet"],
        expected_answer_keywords=["reduced efficacy", "poor metabolizer", "alternative"],
        relevant_titles=["cpic", "clopidogrel", "CYP2C19"],
    ),
    EvalQuery(
        query_id="Q4",
        gene="TPMT",
        drug="azathioprine",
        question="What dose adjustment is needed for TPMT poor metabolizers taking azathioprine?",
        relevant_keywords=["TPMT", "azathioprine", "poor metabolizer", "dose reduction", "myelotoxicity"],
        expected_answer_keywords=["dose reduction", "myelotoxicity", "TPMT"],
        relevant_titles=["cpic", "azathioprine", "TPMT"],
    ),
    EvalQuery(
        query_id="Q5",
        gene="CYP2C9",
        drug="warfarin",
        question="How does CYP2C9 *2 or *3 allele affect warfarin dosing?",
        relevant_keywords=["CYP2C9", "warfarin", "dose", "INR", "bleeding", "reduced"],
        expected_answer_keywords=["dose reduction", "CYP2C9", "warfarin"],
        relevant_titles=["cpic", "warfarin", "CYP2C9"],
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# Relevance judging
# ══════════════════════════════════════════════════════════════════════════════

def _is_relevant(doc_text: str, doc_title: str, query: EvalQuery) -> bool:
    """
    Soft relevance judge.

    A document is deemed relevant if:
      • Its title contains a relevant title fragment, OR
      • At least 2 relevant keywords appear in the doc text.
    """
    title_lower = doc_title.lower()
    text_lower = doc_text.lower()

    # Title match
    for t in query.relevant_titles:
        if t.lower() in title_lower:
            return True

    # Keyword match — at least 2 of the defined relevant keywords
    keyword_hits = sum(1 for kw in query.relevant_keywords if kw.lower() in text_lower)
    return keyword_hits >= 2


# ══════════════════════════════════════════════════════════════════════════════
# Core metric computations
# ══════════════════════════════════════════════════════════════════════════════

KS = [1, 3, 5, 10]  # Evaluate at these k values


def precision_at_k(relevant_flags: List[bool], k: int) -> float:
    """P@K = #relevant in top-k / k"""
    return sum(relevant_flags[:k]) / k if k > 0 else 0.0


def recall_at_k(relevant_flags: List[bool], total_relevant: int, k: int) -> float:
    """R@K = #relevant in top-k / total_relevant"""
    if total_relevant == 0:
        return 0.0
    return sum(relevant_flags[:k]) / total_relevant


def f1_at_k(p: float, r: float) -> float:
    """F1 = 2*P*R / (P+R)"""
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def average_precision(relevant_flags: List[bool]) -> float:
    """
    AP = (1 / |R|) * sum_k( P@k * rel(k) )
    Only non-zero for positions where a relevant doc appears.
    """
    relevant_count = sum(relevant_flags)
    if relevant_count == 0:
        return 0.0
    ap = 0.0
    hits = 0
    for i, rel in enumerate(relevant_flags, start=1):
        if rel:
            hits += 1
            ap += hits / i
    return ap / relevant_count


def reciprocal_rank(relevant_flags: List[bool]) -> float:
    """RR = 1 / rank_of_first_relevant_doc"""
    for i, rel in enumerate(relevant_flags, start=1):
        if rel:
            return 1.0 / i
    return 0.0


def dcg_at_k(relevant_flags: List[bool], k: int) -> float:
    """DCG@K = sum( rel_i / log2(i+1) ) for i in 1..k"""
    return sum(
        rel / math.log2(i + 1)
        for i, rel in enumerate(relevant_flags[:k], start=1)
    )


def ndcg_at_k(relevant_flags: List[bool], k: int) -> float:
    """NDCG@K = DCG@K / IDCG@K"""
    ideal_flags = sorted(relevant_flags[:k], reverse=True)
    idcg = dcg_at_k(ideal_flags, k)
    if idcg == 0:
        return 0.0
    return dcg_at_k(relevant_flags, k) / idcg


def hit_rate_at_k(relevant_flags: List[bool], k: int) -> float:
    """HR@K = 1 if any relevant doc in top-k, else 0"""
    return float(any(relevant_flags[:k]))


# ══════════════════════════════════════════════════════════════════════════════
# Retrieval evaluation
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_retrieval(query: EvalQuery, verbose: bool = False) -> Optional[RetrievalResult]:
    """
    Evaluate retrieval metrics for a single query using ChromaDB + reranker.
    """
    logger.info(f"[{query.query_id}] Evaluating retrieval: {query.question[:60]}…")

    try:
        from services.embeddings import similarity_search_with_filter
        from services.reranker import rerank
    except ImportError as e:
        logger.error(f"Cannot import backend services: {e}")
        return None

    full_query = f"Gene: {query.gene}, Drug: {query.drug}. {query.question}"

    # ── Retrieve top-20 from ChromaDB ──
    try:
        candidates = similarity_search_with_filter(
            query=full_query,
            gene=query.gene,
            drug=query.drug,
            k=20,
        )
    except Exception as e:
        logger.error(f"[{query.query_id}] Retrieval failed: {e}")
        return None

    if not candidates:
        logger.warning(f"[{query.query_id}] No documents retrieved. Is the guideline ingested?")
        return None

    # ── Rerank top-10 ──
    try:
        top_results = rerank(query=full_query, docs_and_scores=candidates, top_n=10)
    except Exception as e:
        logger.warning(f"[{query.query_id}] Reranker failed, using raw results: {e}")
        top_results = sorted(candidates, key=lambda x: x[1], reverse=True)[:10]

    # ── Judge relevance ──
    retrieved_docs = []
    relevant_flags = []

    for doc, score in top_results:
        title = doc.metadata.get("title", "Unknown")
        is_rel = _is_relevant(doc.page_content, title, query)
        relevant_flags.append(is_rel)
        retrieved_docs.append({
            "title": title,
            "score": round(float(score), 4),
            "text_preview": doc.page_content[:150].replace("\n", " "),
            "relevant": is_rel,
        })
        if verbose:
            rel_marker = "✓ RELEVANT" if is_rel else "✗ Not relevant"
            logger.info(f"  [{rel_marker}] score={score:.4f} | {title[:60]}")

    total_relevant = max(sum(relevant_flags), 1)  # floor at 1 to avoid division errors

    # ── Compute all metrics ──
    p_at_k = {k: precision_at_k(relevant_flags, k) for k in KS}
    r_at_k = {k: recall_at_k(relevant_flags, total_relevant, k) for k in KS}
    f_at_k = {k: f1_at_k(p_at_k[k], r_at_k[k]) for k in KS}
    n_at_k = {k: ndcg_at_k(relevant_flags, k) for k in KS}
    h_at_k = {k: hit_rate_at_k(relevant_flags, k) for k in KS}
    ap = average_precision(relevant_flags)
    rr = reciprocal_rank(relevant_flags)

    logger.info(
        f"[{query.query_id}] P@5={p_at_k[5]:.3f}  R@5={r_at_k[5]:.3f}  "
        f"F1@5={f_at_k[5]:.3f}  RR={rr:.3f}  NDCG@5={n_at_k[5]:.3f}"
    )

    return RetrievalResult(
        query_id=query.query_id,
        retrieved_docs=retrieved_docs,
        relevant_count=total_relevant,
        precision_at_k=p_at_k,
        recall_at_k=r_at_k,
        f1_at_k=f_at_k,
        average_precision=ap,
        reciprocal_rank=rr,
        ndcg_at_k=n_at_k,
        hit_rate_at_k=h_at_k,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Generation evaluation
# ══════════════════════════════════════════════════════════════════════════════

def _tokens(text: str) -> set:
    """Extract meaningful tokens (≥4 chars) from text."""
    return set(re.findall(r"\b[a-z]{4,}\b", text.lower()))


def evaluate_generation(query: EvalQuery, verbose: bool = False) -> Optional[GenerationResult]:
    """
    Evaluate end-to-end RAG generation metrics for a single query.
    Calls query_rag() which includes retrieval + reranking + LLM.
    """
    logger.info(f"[{query.query_id}] Evaluating generation (full RAG)…")

    try:
        from services.rag import query_rag
    except ImportError as e:
        logger.error(f"Cannot import rag service: {e}")
        return None

    start = time.perf_counter()
    try:
        result = query_rag(gene=query.gene, drug=query.drug, question=query.question)
    except Exception as e:
        logger.error(f"[{query.query_id}] RAG call failed: {e}")
        return None
    latency = round(time.perf_counter() - start, 2)

    answer = result.get("answer", "")
    metrics = result.get("metrics", {}) or {}
    sources = result.get("sources", [])

    # Expected keyword coverage
    answer_lower = answer.lower()
    found = [kw for kw in query.expected_answer_keywords if kw.lower() in answer_lower]
    missing = [kw for kw in query.expected_answer_keywords if kw.lower() not in answer_lower]
    kw_hit_rate = len(found) / max(len(query.expected_answer_keywords), 1)

    if verbose:
        logger.info(f"  Answer ({len(answer.split())} words): {answer[:200]}…")
        logger.info(f"  Keywords found: {found}")
        logger.info(f"  Keywords missing: {missing}")

    gen_result = GenerationResult(
        query_id=query.query_id,
        answer=answer[:500],  # truncated for storage
        answer_word_count=len(answer.split()),
        context_precision=metrics.get("context_precision", 0.0),
        faithfulness=metrics.get("faithfulness", 0.0),
        answer_relevancy=metrics.get("answer_relevancy", 0.0),
        source_count=metrics.get("source_count", len(sources)),
        latency_seconds=latency,
        expected_keywords_found=found,
        expected_keywords_missing=missing,
        keyword_hit_rate=round(kw_hit_rate, 4),
    )

    logger.info(
        f"[{query.query_id}] faith={gen_result.faithfulness:.3f}  "
        f"ctx_prec={gen_result.context_precision:.3f}  "
        f"relevancy={gen_result.answer_relevancy:.3f}  "
        f"kw_hit={gen_result.keyword_hit_rate:.3f}  "
        f"latency={latency}s"
    )

    return gen_result


# ══════════════════════════════════════════════════════════════════════════════
# Aggregate metrics
# ══════════════════════════════════════════════════════════════════════════════

def aggregate(
    retrieval_results: List[RetrievalResult],
    generation_results: List[GenerationResult],
) -> AggregateMetrics:
    """Compute aggregate metrics across all queries."""

    agg = AggregateMetrics(total_queries=len(retrieval_results))

    # ── Retrieval aggregation ──
    if retrieval_results:
        for k in KS:
            agg.mean_precision[k] = round(
                sum(r.precision_at_k[k] for r in retrieval_results) / len(retrieval_results), 4
            )
            agg.mean_recall[k] = round(
                sum(r.recall_at_k[k] for r in retrieval_results) / len(retrieval_results), 4
            )
            agg.mean_f1[k] = round(
                sum(r.f1_at_k[k] for r in retrieval_results) / len(retrieval_results), 4
            )
            agg.mean_ndcg[k] = round(
                sum(r.ndcg_at_k[k] for r in retrieval_results) / len(retrieval_results), 4
            )
            agg.mean_hit_rate[k] = round(
                sum(r.hit_rate_at_k[k] for r in retrieval_results) / len(retrieval_results), 4
            )

        agg.mrr = round(
            sum(r.reciprocal_rank for r in retrieval_results) / len(retrieval_results), 4
        )
        agg.map_score = round(
            sum(r.average_precision for r in retrieval_results) / len(retrieval_results), 4
        )

    # ── Generation aggregation ──
    if generation_results:
        n = len(generation_results)
        agg.mean_context_precision = round(sum(g.context_precision for g in generation_results) / n, 4)
        agg.mean_faithfulness = round(sum(g.faithfulness for g in generation_results) / n, 4)
        agg.mean_answer_relevancy = round(sum(g.answer_relevancy for g in generation_results) / n, 4)
        agg.mean_latency_seconds = round(sum(g.latency_seconds for g in generation_results) / n, 2)
        agg.mean_keyword_hit_rate = round(sum(g.keyword_hit_rate for g in generation_results) / n, 4)

    return agg


# ══════════════════════════════════════════════════════════════════════════════
# Pretty-print report
# ══════════════════════════════════════════════════════════════════════════════

def print_report(
    agg: AggregateMetrics,
    retrieval_results: List[RetrievalResult],
    generation_results: List[GenerationResult],
):
    sep = "═" * 70

    print(f"\n{sep}")
    print("  CPIC PHARMACOGENOMICS RAG — EVALUATION REPORT")
    print(sep)
    print(f"  Queries evaluated : {agg.total_queries}")
    print()

    print("  ┌─ RETRIEVAL METRICS ──────────────────────────────────────────┐")
    print(f"  │  MRR (Mean Reciprocal Rank)    : {agg.mrr:.4f}")
    print(f"  │  MAP (Mean Average Precision)  : {agg.map_score:.4f}")
    print()
    header = f"  │  {'Metric':<20}" + "".join(f"  @{k:<3}" for k in KS)
    print(header)
    print(f"  │  {'─'*20}" + "─" * 28)

    for label, metric_dict in [
        ("Precision", agg.mean_precision),
        ("Recall",    agg.mean_recall),
        ("F1",        agg.mean_f1),
        ("NDCG",      agg.mean_ndcg),
        ("Hit Rate",  agg.mean_hit_rate),
    ]:
        row = f"  │  {label:<20}" + "".join(f"  {metric_dict.get(k, 0):.3f}" for k in KS)
        print(row)

    print("  └──────────────────────────────────────────────────────────────┘")

    if generation_results:
        print()
        print("  ┌─ GENERATION METRICS (RAGAS-proxy) ───────────────────────────┐")
        print(f"  │  Context Precision    : {agg.mean_context_precision:.4f}")
        print(f"  │  Faithfulness         : {agg.mean_faithfulness:.4f}")
        print(f"  │  Answer Relevancy     : {agg.mean_answer_relevancy:.4f}")
        print(f"  │  Keyword Hit Rate     : {agg.mean_keyword_hit_rate:.4f}")
        print(f"  │  Avg Latency (s)      : {agg.mean_latency_seconds:.2f}s")
        print("  └──────────────────────────────────────────────────────────────┘")

    if retrieval_results:
        print()
        print("  ┌─ PER-QUERY RETRIEVAL BREAKDOWN ───────────────────────────────┐")
        print(f"  │  {'ID':<4} {'P@5':>6} {'R@5':>6} {'F1@5':>6} {'MRR':>6} {'NDCG@5':>8} {'HR@5':>6}")
        print(f"  │  {'─'*4} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*8} {'─'*6}")
        for r in retrieval_results:
            print(
                f"  │  {r.query_id:<4} "
                f"{r.precision_at_k[5]:>6.3f} "
                f"{r.recall_at_k[5]:>6.3f} "
                f"{r.f1_at_k[5]:>6.3f} "
                f"{r.reciprocal_rank:>6.3f} "
                f"{r.ndcg_at_k[5]:>8.3f} "
                f"{r.hit_rate_at_k[5]:>6.1f}"
            )
        print("  └──────────────────────────────────────────────────────────────┘")

    print(f"\n{sep}\n")


# ══════════════════════════════════════════════════════════════════════════════
# Main entrypoint
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval + generation metrics for the CPIC pharmacogenomics RAG pipeline."
    )
    parser.add_argument(
        "--full-rag",
        action="store_true",
        help="Include end-to-end LLM generation evaluation (requires OPENROUTER_API_KEY).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save JSON results (e.g. results/eval_results.json).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-document relevance judgements.",
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        help="Query IDs to evaluate (e.g. --queries Q1 Q3). Default: all.",
    )
    args = parser.parse_args()

    # Filter queries if requested
    queries = EVAL_QUERIES
    if args.queries:
        queries = [q for q in EVAL_QUERIES if q.query_id in args.queries]
        if not queries:
            logger.error(f"No matching query IDs found. Available: {[q.query_id for q in EVAL_QUERIES]}")
            sys.exit(1)

    logger.info(f"Starting evaluation on {len(queries)} queries…")
    logger.info(f"Full RAG (LLM generation): {'YES' if args.full_rag else 'NO (retrieval only)'}")

    retrieval_results: List[RetrievalResult] = []
    generation_results: List[GenerationResult] = []

    for query in queries:
        # ── Retrieval evaluation ──
        ret = evaluate_retrieval(query, verbose=args.verbose)
        if ret:
            retrieval_results.append(ret)

        # ── Generation evaluation (optional, costs API credits) ──
        if args.full_rag:
            gen = evaluate_generation(query, verbose=args.verbose)
            if gen:
                generation_results.append(gen)

    if not retrieval_results:
        logger.error(
            "No retrieval results collected. "
            "Ensure guidelines are ingested and ChromaDB is populated."
        )
        sys.exit(1)

    # ── Aggregate ──
    agg = aggregate(retrieval_results, generation_results)

    # ── Print report ──
    print_report(agg, retrieval_results, generation_results)

    # ── Save JSON ──
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "aggregate": asdict(agg),
            "retrieval_per_query": [asdict(r) for r in retrieval_results],
            "generation_per_query": [asdict(g) for g in generation_results],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Results saved → {output_path.resolve()}")


if __name__ == "__main__":
    main()
