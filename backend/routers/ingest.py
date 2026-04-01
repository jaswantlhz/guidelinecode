"""Ingest router — trigger guideline ingestion pipeline.

REFACTORED: Ingestion now runs as a BackgroundTask (async).
- POST /api/ingest returns 202 Accepted immediately with a task ID
- The actual Unstructured.io parsing + embedding runs in the background
- Poll GET /api/ingest/options for the gene-drug catalog
"""

import uuid
import logging
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from models.schemas import IngestRequest, IngestResponse
from services.ingestion import ingest_drug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ingest"])

# In-memory job store (sufficient for single-server dev; use Redis in production)
_jobs: Dict[str, dict] = {}


def _run_ingest_job(job_id: str, gene: str, drug: str) -> None:
    """Background worker — runs ingest_drug and stores result in _jobs."""
    try:
        _jobs[job_id]["status"] = "running"
        result = ingest_drug(gene=gene, drug=drug)
        _jobs[job_id].update(result)
    except Exception as e:
        logger.error(f"Background ingest job {job_id} failed: {e}")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["message"] = str(e)


@router.post("/ingest", status_code=202)
async def post_ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    Start a guideline ingestion job asynchronously.

    Returns 202 Accepted immediately. The ingestion pipeline runs in the
    background. Use GET /api/ingest/status?gene=...&drug=... to poll.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "pending",
        "message": f"Ingestion started for {req.gene}/{req.drug}",
        "guideline_id": None,
    }

    background_tasks.add_task(_run_ingest_job, job_id, req.gene, req.drug)
    logger.info(f"Ingestion job {job_id} queued for {req.gene}/{req.drug}")

    return {"status": "pending", "message": f"Ingestion started for {req.gene}/{req.drug}", "job_id": job_id}


@router.get("/ingest/job/{job_id}")
async def get_job_status(job_id: str):
    """Poll the status of a specific background ingest job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@router.get("/ingest/status")
async def get_ingest_status(gene: str, drug: str):
    """Check if a gene/drug guideline has been ingested (by querying ChromaDB)."""
    from services.embeddings import get_vectorstore
    vs = get_vectorstore()
    if vs is None:
        return IngestResponse(status="not_found", message="No guidelines have been ingested yet.")
    try:
        results = vs._collection.get(
            where={"$and": [{"gene": {"$eq": gene}}, {"drug": {"$eq": drug.lower()}}]},
            limit=1,
        )
        if results.get("ids"):
            return IngestResponse(
                status="completed",
                message=f"Guideline for {gene}/{drug} is already ingested.",
                guideline_id=f"{gene}_{drug}",
            )
        return IngestResponse(status="not_found", message=f"No guideline found for {gene}/{drug}.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/options")
async def get_ingest_options():
    """Get all available gene-drug pairs from the CPIC spreadsheet."""
    try:
        import pandas as pd
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent
        file_path = base_dir / "agent" / "tools" / "cpic_gene-drug_pairs.xlsx"

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_excel(file_path)

        genes = sorted(df["Gene"].dropna().unique().tolist())
        drugs = sorted(df["Drug"].dropna().unique().tolist())
        pairs = df[["Gene", "Drug"]].dropna().to_dict(orient="records")

        return {"genes": genes, "drugs": drugs, "pairs": pairs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
