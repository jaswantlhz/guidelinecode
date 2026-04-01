"""Query router — RAG-powered Q&A endpoint."""

from fastapi import APIRouter, HTTPException
from models.schemas import QueryRequest, QueryResponse, Source, RagasMetrics
from services.rag import query_rag

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def post_query(req: QueryRequest):
    try:
        result = query_rag(
            gene=req.gene or "",
            drug=req.drug or "",
            question=req.question,
        )

        sources = []
        for src in result.get("sources", []):
            sources.append(Source(
                title=src.get("title", ""),
                section=src.get("section"),
                page=src.get("page", 0),
                text=src.get("text", ""),
                score=src.get("score", 0.0),
                pmid=src.get("pmid"),
            ))

        metrics_data = result.get("metrics")
        metrics = RagasMetrics(**metrics_data) if metrics_data else None

        return QueryResponse(
            answer=result.get("answer", ""),
            model_used=result.get("model_used", "openrouter"),
            sources=sources,
            metrics=metrics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

