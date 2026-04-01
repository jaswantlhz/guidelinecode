"""Reranker service — Cross-encoder reranking for improved retrieval precision.

After ChromaDB returns top-K candidate chunks, this service re-scores
them against the user's actual question using a cross-encoder model.
Cross-encoders are far more accurate than bi-encoders for relevance
scoring because they jointly encode the query AND document.

Model: BAAI/bge-reranker-base (~280MB, runs on CPU)
"""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_reranker = None


def get_reranker():
    """Lazy-load the cross-encoder reranker."""
    global _reranker
    if _reranker is not None:
        return _reranker

    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
        logger.info("Cross-encoder reranker loaded: BAAI/bge-reranker-base")
    except ImportError:
        logger.warning("sentence-transformers not installed. Reranking disabled.")
        _reranker = None
    except Exception as e:
        logger.error(f"Failed to load reranker: {e}")
        _reranker = None

    return _reranker


def rerank(
    query: str,
    docs_and_scores: List[tuple[Document, float]],
    top_n: int = 5,
) -> List[tuple[Document, float]]:
    """
    Re-rank retrieved documents using a cross-encoder.

    Args:
        query: The user's actual question.
        docs_and_scores: Initial retrieval results from ChromaDB.
        top_n: How many to return after reranking.

    Returns:
        Top-N documents sorted by cross-encoder relevance score.
    """
    if not docs_and_scores:
        return []

    reranker = get_reranker()
    if reranker is None:
        # Fallback: return top_n from original ranking
        logger.warning("Reranker unavailable. Using vector similarity ranking.")
        return sorted(docs_and_scores, key=lambda x: x[1], reverse=True)[:top_n]

    # Build query-document pairs for the cross-encoder
    docs = [d for d, _ in docs_and_scores]
    pairs = [(query, doc.page_content) for doc in docs]

    try:
        scores = reranker.predict(pairs)
    except Exception as e:
        logger.error(f"Reranking failed: {e}. Using vector similarity fallback.")
        return sorted(docs_and_scores, key=lambda x: x[1], reverse=True)[:top_n]

    # Combine docs with reranker scores and sort descending
    reranked = sorted(
        zip(docs, scores),
        key=lambda x: float(x[1]),
        reverse=True,
    )

    # Return top_n as (Document, score) tuples, normalizing score to 0-1
    results = []
    for doc, score in reranked[:top_n]:
        # Cross-encoder outputs logits, sigmoid converts to 0-1 probability
        import math
        normalized = 1.0 / (1.0 + math.exp(-float(score)))
        results.append((doc, round(normalized, 4)))

    return results
