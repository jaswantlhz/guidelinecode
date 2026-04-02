"""Ingest router — trigger guideline ingestion pipeline.

REFACTORED: Ingestion now runs as a BackgroundTask (async).
- POST /api/ingest returns 202 Accepted immediately with a task ID
- The actual Unstructured.io parsing + embedding runs in the background
- Poll GET /api/ingest/job/<job_id> to get status + progress
"""

import asyncio
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from fastapi import APIRouter, HTTPException
from models.schemas import IngestRequest, IngestResponse
from services.ingestion import ingest_drug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ingest"])

# In-memory job store (sufficient for single-server dev; use Redis in production)
_jobs: Dict[str, dict] = {}

# Thread pool for running sync ingestion without blocking the async event loop
_executor = ThreadPoolExecutor(max_workers=2)


# Pipeline step labels for progress tracking
_STEPS = [
    "Checking existing index",
    "Locating guideline PDF",
    "Downloading PDF",
    "Parsing with Unstructured.io",
    "Fetching PubMed abstracts",
    "Storing in MongoDB",
    "Embedding in ChromaDB",
    "Done",
]


def _progress(job_id: str, step_index: int, message: str) -> None:
    """Update the job's progress fields."""
    _jobs[job_id]["step"] = _STEPS[step_index]
    _jobs[job_id]["step_index"] = step_index
    _jobs[job_id]["total_steps"] = len(_STEPS) - 1  # exclude 'Done'
    _jobs[job_id]["message"] = message


def _run_ingest_job(job_id: str, gene: str, drug: str) -> None:
    """
    Background worker — runs ingest_drug with granular step tracking.
    Runs in a thread pool to avoid blocking the async event loop.
    """
    try:
        _jobs[job_id]["status"] = "running"
        _progress(job_id, 0, f"Checking if {gene}/{drug} is already indexed…")
        result = ingest_drug(gene=gene, drug=drug, _progress_cb=lambda i, m: _progress(job_id, i, m))
        _jobs[job_id].update(result)
        _progress(job_id, len(_STEPS) - 1, result.get("message", "Done"))
    except Exception as e:
        logger.error(f"Background ingest job {job_id} failed: {e}")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["message"] = str(e)


@router.post("/ingest", status_code=202)
async def post_ingest(req: IngestRequest):
    """
    Start a guideline ingestion job asynchronously.

    Returns 202 Accepted immediately. The ingestion pipeline runs in a
    thread pool executor so the async event loop is never blocked.
    Use GET /api/ingest/job/<job_id> to poll progress.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "message": f"Queued ingestion for {req.gene}/{req.drug}",
        "guideline_id": None,
        "step": "Queued",
        "step_index": 0,
        "total_steps": len(_STEPS) - 1,
    }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_ingest_job, job_id, req.gene, req.drug)
    logger.info(f"Ingestion job {job_id} dispatched to thread pool for {req.gene}/{req.drug}")

    return {
        "status": "pending",
        "message": f"Queued ingestion for {req.gene}/{req.drug}",
        "job_id": job_id,
        "step": "Queued",
        "step_index": 0,
        "total_steps": len(_STEPS) - 1,
    }


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
