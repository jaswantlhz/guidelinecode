"""RAG service — LangChain chain for pharmacogenomics Q&A.

Uses FAISS similarity_search_with_score directly so we get actual
relevance scores, then feeds the results to the LLM for answering.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from config import settings
from services.embeddings import get_vectorstore
import mlflow

SYSTEM_PROMPT = """You are a clinical pharmacogenomics expert. Answer the
question using ONLY the provided guideline excerpts. If the information
is not in the context, say so clearly. Always cite the guideline source.

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
    """Get LLM configured for OpenRouter or direct OpenAI."""
    global _llm
    if _llm is not None:
        return _llm

    _llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "CPIC RAG",
        },
    )
    return _llm


def query_rag(gene: str, drug: str, question: str) -> dict:
    """Run RAG query with actual similarity scores and computed confidence."""
    
    # Enable MLflow tracking for queries
    with mlflow.start_run(run_name=f"rag_query_{gene}_{drug}"):
        mlflow.log_param("gene", gene)
        mlflow.log_param("drug", drug)
        mlflow.log_param("question", question)
        
        vs = get_vectorstore()
    if vs is None:
        return {
            "answer": "No guidelines have been indexed yet. Please ingest a guideline first.",
            "sources": [],
            "confidence": 0.0,
            "model_used": "none",
        }

    # ── Step 1: Retrieve documents WITH scores ──
    full_question = f"Gene: {gene}, Drug: {drug}. {question}"
    docs_and_scores = vs.similarity_search_with_score(full_question, k=5)

    if not docs_and_scores:
        return {
            "answer": "No relevant guideline sections found for your query.",
            "sources": [],
            "confidence": 0.0,
            "model_used": settings.LLM_MODEL,
        }

    # ── Step 2: Build context from retrieved docs ──
    context_parts = []
    sources = []
    raw_scores = []

    for doc, score in docs_and_scores:
        # FAISS returns L2 distance — lower = more similar
        # Convert to a 0-1 similarity: sim = 1 / (1 + distance)
        similarity = 1.0 / (1.0 + float(score))
        raw_scores.append(similarity)

        context_parts.append(doc.page_content)
        sources.append({
            "title": doc.metadata.get("title", "Unknown"),
            "page": doc.metadata.get("page", 0),
            "section": doc.metadata.get("element_type", None),
            "snippet": doc.page_content[:300],
            "text": doc.page_content[:300],
            "score": round(similarity, 3),
        })

    context = "\n\n---\n\n".join(context_parts)

    # ── Step 3: Compute confidence from scores ──
    # Average of top-k similarity scores
    avg_score = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
    # Scale to a more intuitive 0-1 range (scores typically ~0.3-0.8)
    confidence = min(1.0, avg_score * 1.2)

    prompt = PromptTemplate(
        template=SYSTEM_PROMPT,
        input_variables=["context", "question"],
    )
    formatted = prompt.format(context=context, question=full_question)

    # ── Step 4: Call LLM with Fallback ──
    models_to_try = [settings.LLM_MODEL] + settings.LLM_FALLBACKS
    final_answer = ""
    used_model = "none"
    last_error = None

    import time
    from langchain_core.messages import HumanMessage

    for model_name in models_to_try:
        try:
            print(f"Trying LLM model: {model_name}...")
            # Create a localized LLM instance for this attempt
            llm = ChatOpenAI(
                model=model_name,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "CPIC RAG",
                },
            )
            
            response = llm.invoke(formatted)
            final_answer = response.content if hasattr(response, "content") else str(response)
            used_model = model_name
            print(f"Success with model: {model_name}")
            break
        except Exception as e:
            error_msg = str(e)
            print(f"Failed with model {model_name}: {error_msg}")
            last_error = e
            # If 429 (rate limit), maybe sleep briefly? 
            # But better to just move to next model immediately for speed.
        continue

    if not final_answer and last_error:
        # particular case: if all failed, return a friendly message instead of crashing
        final_answer = f"I'm sorry, I tried {len(models_to_try)} different AI models but they are all currently overloaded or unavailable (Free Tier limitations). Please try again in 1 minute. Last error: {str(last_error)}"
        confidence = 0.0

    # Log final metrics and params to MLflow
    mlflow.log_param("used_model", used_model)
    mlflow.log_metric("confidence", round(confidence, 2))
    mlflow.log_metric("retrieved_sources_count", len(sources))
    if sources:
        mlflow.log_metric("top_source_score", sources[0].get("score", 0))

    return {
        "answer": final_answer,
        "sources": sources,
        "confidence": round(confidence, 2),
        "model_used": used_model,
    }
