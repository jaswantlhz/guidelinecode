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


@router.get("/ingest/options")
async def get_ingest_options():
    try:
        import pandas as pd
        from pathlib import Path

        # Path to the Excel file relative to this file
        # backend/routers/ingest.py -> backend/routers/ -> backend/ -> guidelinecode/ -> agent/tools/
        base_dir = Path(__file__).resolve().parent.parent.parent
        file_path = base_dir / "agent" / "tools" / "cpic_gene-drug_pairs.xlsx"

        if not file_path.exists():
             raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_excel(file_path)
        
        # Get unique values and sort them
        genes = sorted(df["Gene"].dropna().unique().tolist())
        drugs = sorted(df["Drug"].dropna().unique().tolist())
        
        # Get all valid pairs
        pairs = df[["Gene", "Drug"]].dropna().to_dict(orient="records")

        return {"genes": genes, "drugs": drugs, "pairs": pairs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
