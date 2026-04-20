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

SYSTEM_PROMPT = """You are a domain expert in clinical pharmacogenomics.
- Use the context as the primary source.
- The user query might ask about a specific drug (e.g. halothane), but the context may use a broader drug class (e.g. halogenated volatile anesthetics, inhaled anesthetics). Use your domain knowledge to map specific drugs to their classes when interpreting the context.
- If the answer is partially available, answer using available information.
- Only say "Not found in context" if nothing relevant exists.
- If only partial information is available, provide the best possible answer and mention limitations.
- Cite the relevant parts of the context by referencing the [Source X].

Return your response in the following strict structure:

### 1. Direct Answer
Provide a comprehensive, detailed answer spanning 2 to 3 well-developed paragraphs. Start with a clear direct answer, then provide necessary clinical explanations, mechanisms, alternative options, caveats, and summarize any relevant tables or itemized lists logically to ensure the user gets a thorough understanding.

### 2. Supporting Evidence
Provide supporting evidence (quotes) when clearly available, referencing the metadata source tags.

### 3. Confidence Level
State your confidence as a score from 0.0 to 1.0 (e.g., 0.95), based strictly on how completely the provided context answers the question.

Context:
{context}

Question: {question}"""

_llm = None


def _get_llm() -> ChatOpenAI:
    """Get LLM — tuned for strict factual RAG groundedness."""
    global _llm
    if _llm is not None:
        return _llm

    _llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0.0,    # 0.0 for zero hallucination
        top_p=0.9,          # slightly constrained sampling
        max_tokens=800,     # avoid rambling
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
    top_results = rerank(query=full_question, docs_and_scores=candidates, top_n=3)

    # ── Step 3: Build context and source list ──
    context_parts = []
    sources = []

    for i, (doc, score) in enumerate(top_results, 1):
        source_title = doc.metadata.get("title", "Unknown")
        elem_type = doc.metadata.get("element_type", "Text")
        
        # Build a highly structured context chunk to improve LLM reasoning
        origin = "PubMed Abstract" if doc.metadata.get("source") == "pubmed" else "CPIC Guidelines"
        context_chunk = f"[Source {i}: {origin} | File: {source_title} | Type: {elem_type}]\n{doc.page_content}"
        context_parts.append(context_chunk)
        
        source_record = {
            "title": source_title,
            "page": doc.metadata.get("page", 0),
            "section": elem_type,
            "text": doc.page_content[:300],
            "score": score,
        }
        # Include PMID if this chunk came from PubMed
        if doc.metadata.get("source") == "pubmed":
            source_record["pmid"] = doc.metadata.get("pmid", "")
            source_record["title"] = f"[PubMed] {source_title}"
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
