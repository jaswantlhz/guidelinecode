"""Ingestion service — Full pipeline from gene+drug to embedded vectors.

Pipeline:
1. Receive gene + drug from the API
2. Check MongoDB for an already-ingested guideline → skip if exists
3. Look up the CPIC guideline URL from the Excel spreadsheet (agent tool)
4. Scrape the page for a PDF download link (agent tool)
5. Download the PDF (agent tool)
6. Parse the PDF with Unstructured.io API → structured JSON
7. Store the parsed JSON in MongoDB
8. Convert elements → LangChain Documents → embed in FAISS
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, List

from langchain_core.documents import Document

from config import settings
from services.embeddings import add_documents
from services.metadata import add_guideline
from services.mongodb import get_guideline, store_guideline
from services.unstructured_parser import parse_pdf_with_unstructured

logger = logging.getLogger(__name__)

# ─── Agent tools (imported from the agent directory) ─────
AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agent"
TOOLS_DIR = AGENT_DIR / "tools"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from tools.guideline_fetching import get_guideline_pdf
from tools.link_searcher import search_pdf
from tools.pdf_retriver import download_pdf


# ─── Convert Unstructured elements → LangChain Documents ─

def _elements_to_documents(
    elements: list[dict[str, Any]],
    gene: str,
    drug: str,
) -> List[Document]:
    """Convert Unstructured.io JSON elements into LangChain Document objects."""
    docs = []
    for elem in elements:
        text = elem.get("text", "").strip() if isinstance(elem, dict) else str(elem).strip()
        if not text or len(text) < 20:
            continue

        metadata = elem.get("metadata", {}) if isinstance(elem, dict) else {}
        elem_type = elem.get("type", "") if isinstance(elem, dict) else ""

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "title": metadata.get("filename", f"{gene}_{drug}"),
                    "page": metadata.get("page_number", 0),
                    "source": "unstructured_api",
                    "drug": drug,
                    "gene": gene,
                    "element_type": elem_type,
                },
            )
        )
    return docs


# ─── Agent pipeline: fetch guideline PDF ─────────────────

def _fetch_guideline_pdf(gene: str, drug: str) -> Path | None:
    """Run the agent tool pipeline to fetch the CPIC guideline PDF."""
    try:
        logger.info(f"Looking up guideline URL for {gene}/{drug}...")
        page_url = get_guideline_pdf(gene=gene, drug=drug)
        logger.info(f"Found guideline page: {page_url}")

        logger.info(f"Searching for PDF link on {page_url}...")
        pdf_url = search_pdf(page_url=page_url)
        logger.info(f"Found PDF link: {pdf_url}")

        pdf_dir = str(settings.PDF_DIR)
        os.makedirs(pdf_dir, exist_ok=True)
        logger.info(f"Downloading PDF to {pdf_dir}...")
        pdf_path = download_pdf(pdf_url=pdf_url, gene=gene, drug=drug, folder=pdf_dir)
        logger.info(f"Downloaded PDF: {pdf_path}")

        return Path(pdf_path)

    except ValueError as e:
        logger.warning(f"Agent pipeline error for {gene}/{drug}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in agent pipeline for {gene}/{drug}: {e}")
        return None


# ─── Find existing PDF ───────────────────────────────────

def _find_pdf(drug_name: str) -> Path | None:
    """Find a PDF matching the drug name in the pdfs directory."""
    pdf_dir = settings.PDF_DIR
    if not pdf_dir.exists():
        return None
    for f in pdf_dir.glob("*.pdf"):
        if drug_name.lower() in f.stem.lower():
            return f
    return None


# ─── Main ingestion entry point ──────────────────────────

def ingest_drug(gene: str, drug: str) -> dict:
    """Ingest a drug guideline — full pipeline.

    1. Check MongoDB for existing guideline → skip if already ingested
    2. Look for existing PDF in backend/pdfs/
    3. If no PDF, fetch via the agent pipeline
    4. Parse with Unstructured.io API
    5. Store JSON in MongoDB
    6. Embed in FAISS for RAG
    """
    drug_name = drug

    # ── Step 1: Check if already ingested ──
    existing = get_guideline(gene=gene, drug=drug_name)
    if existing:
        logger.info(f"Guideline for {gene}/{drug_name} already exists in MongoDB")
        return {
            "status": "completed",
            "message": f"Guideline for {gene}/{drug_name} is already ingested ({existing.get('chunks_count', 0)} chunks).",
            "guideline_id": f"{gene}_{drug_name}_{existing['_id']}",
        }

    # ── Step 2: Find or fetch the PDF ──
    pdf_path = _find_pdf(drug_name)

    if pdf_path is None:
        logger.info(f"No existing PDF for {drug_name}. Running agent pipeline...")
        pdf_path = _fetch_guideline_pdf(gene=gene, drug=drug_name)

    if pdf_path is None:
        return {
            "status": "failed",
            "message": (
                f"Could not find or fetch a guideline PDF for '{gene}/{drug_name}'. "
                f"The gene-drug pair may not exist in the CPIC database."
            ),
        }

    # ── Step 3: Parse with Unstructured.io API ──
    logger.info(f"Parsing '{pdf_path.name}' with Unstructured.io API...")
    try:
        elements = parse_pdf_with_unstructured(pdf_path)
    except Exception as e:
        logger.error(f"Unstructured API failed: {e}")
        return {
            "status": "failed",
            "message": f"Unstructured.io API failed to parse '{pdf_path.name}': {e}",
        }

    if not elements:
        return {
            "status": "failed",
            "message": f"Unstructured.io returned no elements for '{pdf_path.name}'.",
        }

    # ── Step 4: Convert to LangChain Documents ──
    docs = _elements_to_documents(elements, gene=gene, drug=drug_name)
    if not docs:
        return {
            "status": "failed",
            "message": f"No meaningful text extracted from '{pdf_path.name}'.",
        }

    # ── Step 5: Store in MongoDB ──
    guideline_id = store_guideline(
        gene=gene,
        drug=drug_name,
        title=pdf_path.stem,
        pdf_path=str(pdf_path),
        chunks_count=len(docs),
        unstructured_elements=elements,
    )
    logger.info(f"Stored guideline in MongoDB: {guideline_id}")

    # ── Step 6: Embed in FAISS ──
    chunks_added = add_documents(docs)
    logger.info(f"Embedded {chunks_added} chunks in FAISS")

    return {
        "status": "completed",
        "message": (
            f"Fetched, parsed, and ingested '{pdf_path.name}': "
            f"{len(elements)} elements → {chunks_added} chunks embedded."
        ),
        "guideline_id": guideline_id,
    }
