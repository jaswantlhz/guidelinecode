"""Query router — RAG-powered Q&A endpoint."""

from fastapi import APIRouter, HTTPException
from models.schemas import QueryRequest, QueryResponse, Source
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

        # Map sources to the Source schema
        sources = []
        for src in result.get("sources", []):
            sources.append(Source(
                title=src.get("title", ""),
                section=src.get("section"),
                page=src.get("page", 0),
                text=src.get("snippet", src.get("text", "")),
                snippet=src.get("snippet", ""),
                score=src.get("score", 0.0),
            ))

        return QueryResponse(
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0.7),
            model_used=result.get("model_used", "openrouter"),
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
