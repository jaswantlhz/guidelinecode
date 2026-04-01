from pydantic import BaseModel
from typing import Optional, List


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
    score: float = 0.0
    pmid: Optional[str] = None  # Set if source is from PubMed


class RagasMetrics(BaseModel):
    """Proxy RAGAS-style metrics computed from retrieval & generation pipeline."""
    context_precision: float = 0.0   # Average reranker score of top-K sources
    faithfulness: float = 0.0        # Ratio of answer tokens grounded in sources
    answer_relevancy: float = 0.0    # Proxy: answer density relative to context
    source_count: int = 0            # Number of sources used


class QueryResponse(BaseModel):
    answer: str
    model_used: str = "openrouter"
    sources: List[Source] = []
    metrics: Optional[RagasMetrics] = None


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
