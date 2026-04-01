"""RAG service — Pharmacogenomics Q&A with ChromaDB + Reranker.

Pipeline:
1. ChromaDB retrieves top-20 candidates with STRICT gene+drug metadata filter
2. Cross-encoder reranker scores top-20, returns top-5 by true relevance
3. Top-5 chunks are sent to LLM with structured clinical prompt

REMOVED:
- Fake confidence score (was 1/(1+d) * 1.2 — completely dishonest)
- Duplicate snippet/text fields in sources
"""

from __future__ import annotations

import logging
import math
import re
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from config import settings
from services.embeddings import similarity_search_with_filter
from services.reranker import rerank

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a clinical pharmacogenomics expert. Answer the
question using ONLY the provided guideline excerpts and PubMed abstracts.
If the information is not in the context, say so clearly. Always cite the
guideline source or PMID where applicable.

Be precise about dosing recommendations, gene-drug interactions,
phenotype classifications, and activity scores.

When the data supports it, format your answer with:
- A summary table (using markdown table syntax) for phenotype-based recommendations
- Key points as a numbered or bulleted list
- Bold (**text**) for critical values like dose adjustments

Context:
{context}

Question: {question}

Answer:"""

_llm = None


def _get_llm() -> ChatOpenAI:
    """Get LLM — prefers OpenRouter but configurable."""
    global _llm
    if _llm is not None:
        return _llm

    _llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    return _llm


def query_rag(gene: str, drug: str, question: str) -> dict:
    """
    Run RAG query with metadata-filtered retrieval and cross-encoder reranking.

    Steps:
      1. ChromaDB: retrieve top-20 chunks filtered to gene+drug
      2. Reranker: re-score and return top-5 by actual relevance
      3. LLM: generate answer from top-5 chunks
    """
    full_question = f"Gene: {gene}, Drug: {drug}. {question}"

    # ── Step 1: Metadata-filtered retrieval from ChromaDB ──
    candidates = similarity_search_with_filter(
        query=full_question,
        gene=gene,
        drug=drug,
        k=20,  # retrieve 20, then rerank to 5
    )

    if not candidates:
        return {
            "answer": "No relevant guideline sections found for your query. "
                      "Please ingest the guideline for this gene-drug pair first.",
            "sources": [],
            "model_used": settings.LLM_MODEL,
        }

    # ── Step 2: Cross-encoder reranking ──
    top_results = rerank(query=full_question, docs_and_scores=candidates, top_n=5)

    # ── Step 3: Build context and source list ──
    context_parts = []
    sources = []

    for doc, score in top_results:
        context_parts.append(doc.page_content)
        source_record = {
            "title": doc.metadata.get("title", "Unknown"),
            "page": doc.metadata.get("page", 0),
            "section": doc.metadata.get("element_type", None),
            "text": doc.page_content[:300],
            "score": score,
        }
        # Include PMID if this chunk came from PubMed
        if doc.metadata.get("source") == "pubmed":
            source_record["pmid"] = doc.metadata.get("pmid", "")
            source_record["title"] = f"[PubMed] {source_record['title']}"
        sources.append(source_record)

    context = "\n\n---\n\n".join(context_parts)

    # ── Step 4: Call LLM ──
    prompt = PromptTemplate(
        template=SYSTEM_PROMPT,
        input_variables=["context", "question"],
    )
    llm = _get_llm()
    formatted = prompt.format(context=context, question=full_question)
    response = llm.invoke(formatted)
    answer = response.content if hasattr(response, "content") else str(response)

    # ── Step 5: Compute RAGAS-style proxy metrics ──
    reranker_scores = [s for _, s in top_results]
    context_precision = round(sum(reranker_scores) / len(reranker_scores), 4) if reranker_scores else 0.0

    # Faithfulness: what fraction of unique answer tokens appear in any source chunk
    def _tokens(text: str) -> set:
        return set(re.findall(r"\b[a-z]{4,}\b", text.lower()))

    answer_tokens = _tokens(answer)
    context_tokens: set = set()
    for part in context_parts:
        context_tokens |= _tokens(part)
    faithfulness = round(len(answer_tokens & context_tokens) / max(len(answer_tokens), 1), 4)
    faithfulness = min(faithfulness, 1.0)

    # Answer relevancy proxy: logistic of (answer_len / max_context_len)
    answer_len = len(answer.split())
    context_len = sum(len(p.split()) for p in context_parts)
    relevancy_ratio = answer_len / max(context_len, 1)
    answer_relevancy = round(1.0 / (1.0 + math.exp(-6 * (relevancy_ratio - 0.3))), 4)
    answer_relevancy = min(answer_relevancy, 1.0)

    return {
        "answer": answer,
        "sources": sources,
        "model_used": settings.LLM_MODEL,
        "metrics": {
            "context_precision": context_precision,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "source_count": len(top_results),
        },
    }
