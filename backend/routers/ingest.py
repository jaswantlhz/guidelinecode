"""Ingest router — trigger guideline ingestion pipeline."""

from fastapi import APIRouter, HTTPException
from models.schemas import IngestRequest, IngestResponse
from services.ingestion import ingest_drug

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def post_ingest(req: IngestRequest):
    try:
        result = ingest_drug(gene=req.gene, drug=req.drug)
        return IngestResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
