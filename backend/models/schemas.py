from pydantic import BaseModel
from typing import Optional


# ─── Query ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    gene: Optional[str] = None
    drug: Optional[str] = None


class Source(BaseModel):
    title: Optional[str] = ""
    section: Optional[str] = None
    page: Optional[int] = 0
    text: str = ""
    snippet: Optional[str] = ""
    score: float = 0.0


class QueryResponse(BaseModel):
    answer: str
    confidence: float = 0.0
    model_used: str = "openrouter"
    sources: list[Source] = []


# ─── Ingest ────────────────────────────────────────────────
class IngestRequest(BaseModel):
    gene: str
    drug: str


class IngestResponse(BaseModel):
    status: str
    message: str = ""
    guideline_id: Optional[str] = None


# ─── Phenotype ─────────────────────────────────────────────
class PhenotypeRequest(BaseModel):
    gene: str
    diplotype: str


class PhenotypeResponse(BaseModel):
    gene: str
    diplotype: str
    phenotype: str = "Unknown"
    activity_score: Optional[float] = None
    recommendation: str = ""
    ehr_priority: str = ""
    description: str = ""


# ─── Guideline Chunk (internal) ────────────────────────────
class GuidelineChunk(BaseModel):
    drug: str
    gene: str = ""
    title: str = ""
    page: int = 0
    content: str = ""


# ─── Status ────────────────────────────────────────────────
class StatusResponse(BaseModel):
    status: str = "ok"
    indexed_guidelines: int = 0
    total_chunks: int = 0
    embedding_model: str = "all-MiniLM-L6-v2"
