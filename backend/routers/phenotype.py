"""Phenotype router — genotype-to-phenotype lookup via CPIC API."""

from fastapi import APIRouter, HTTPException
from models.schemas import PhenotypeRequest, PhenotypeResponse
from services.phenotype import lookup_phenotype, get_available_genes, get_diplotypes_for_gene

router = APIRouter(prefix="/api/phenotype", tags=["phenotype"])


@router.post("/resolve", response_model=PhenotypeResponse)
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


@router.get("/diplotypes")
async def get_diplotypes(gene: str):
    """Get all unique diplotypes for a given gene."""
    diplotypes = get_diplotypes_for_gene(gene)
    return {"diplotypes": diplotypes}


@router.get("/drugs")
async def get_drugs(gene: str | None = None):
    """Get list of drugs available in CPIC. Optionally filtered by gene."""
    from services.phenotype import get_available_drugs, get_drugs_for_gene
    
    if gene:
         drugs = get_drugs_for_gene(gene)
    else:
         drugs = get_available_drugs()
         
    return {"drugs": drugs}
