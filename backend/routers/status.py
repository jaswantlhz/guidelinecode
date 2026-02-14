"""Status router — pipeline health and indexed guideline info."""

from fastapi import APIRouter
from models.schemas import StatusResponse
from services.embeddings import get_total_chunks
from services.metadata import get_indexed_count
from config import settings

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status():
    return StatusResponse(
        status="ok",
        indexed_guidelines=get_indexed_count(),
        total_chunks=get_total_chunks(),
        embedding_model=settings.EMBEDDING_MODEL,
    )
