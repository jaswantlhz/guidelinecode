"""Phenotype router — genotype-to-phenotype lookup via CPIC API."""

from fastapi import APIRouter, HTTPException
from models.schemas import PhenotypeRequest, PhenotypeResponse
from services.phenotype import lookup_phenotype, get_available_genes, get_diplotypes_for_gene

router = APIRouter(prefix="/api", tags=["phenotype"])


@router.post("/phenotype", response_model=PhenotypeResponse)
async def post_phenotype(req: PhenotypeRequest):
    try:
        result = lookup_phenotype(gene=req.gene, diplotype=req.diplotype)
        return PhenotypeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/genes")
async def get_genes():
    """Get list of genes available in the CPIC diplotype database."""
    genes = get_available_genes()
    return {"genes": genes}


@router.get("/diplotypes/{gene}")
async def get_diplotypes(gene: str):
    """Get all unique diplotypes for a given gene."""
    diplotypes = get_diplotypes_for_gene(gene)
    return {"diplotypes": diplotypes}
