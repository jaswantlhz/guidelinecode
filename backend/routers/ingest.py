"""Ingest router — trigger guideline ingestion pipeline."""

from fastapi import APIRouter, HTTPException
from models.schemas import IngestRequest, IngestResponse
from pipelines.ingest_pipeline import cpic_ingestion_pipeline

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def post_ingest(req: IngestRequest):
    try:
        # Trigger ZenML pipeline
        guideline_id = cpic_ingestion_pipeline(gene=req.gene, drug=req.drug)
        return IngestResponse(**{
            "status": "completed",
            "message": f"ZenML pipeline completed for {req.gene}/{req.drug}.",
            "guideline_id": guideline_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.get("/ingest/status", response_model=IngestResponse)
async def get_ingest_status(gene: str, drug: str):
    from services.mongodb import get_guideline
    
    try:
        existing = get_guideline(gene=gene, drug=drug)
        if existing:
            return {
                "status": "completed",
                "message": f"Guideline for {gene}/{drug} is ingested.",
                "guideline_id": str(existing.get("_id", "")),
            }
        
        return {
            "status": "pending", 
            "message": "Guideline not found in database. It may be processing or not yet started.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
