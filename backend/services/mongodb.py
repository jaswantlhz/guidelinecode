"""MongoDB service — connection and CRUD for guideline storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection

from config import settings

logger = logging.getLogger(__name__)

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Get or create the MongoDB client singleton."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
        logger.info(f"Connected to MongoDB at {settings.MONGODB_URI}")
    return _client


def get_db():
    """Get the application database."""
    return get_client()[settings.MONGODB_DB_NAME]


def _guidelines_col() -> Collection:
    return get_db()["guidelines"]


# ─── Guidelines CRUD ─────────────────────────────────────

def store_guideline(
    gene: str,
    drug: str,
    title: str,
    pdf_path: str,
    chunks_count: int,
    unstructured_elements: list[dict[str, Any]] | None = None,
) -> str:
    """Store a parsed guideline in MongoDB.

    Returns the guideline_id string.
    """
    doc = {
        "gene": gene,
        "drug": drug,
        "title": title,
        "pdf_path": pdf_path,
        "chunks_count": chunks_count,
        "elements": unstructured_elements or [],
        "element_count": len(unstructured_elements) if unstructured_elements else 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = _guidelines_col().insert_one(doc)
    guideline_id = f"{gene}_{drug}_{result.inserted_id}"
    logger.info(f"Stored guideline {guideline_id} ({chunks_count} chunks)")
    return guideline_id


def get_guideline(gene: str, drug: str) -> dict | None:
    """Get a stored guideline by gene + drug."""
    return _guidelines_col().find_one(
        {"gene": {"$regex": f"^{gene}$", "$options": "i"},
         "drug": {"$regex": f"^{drug}$", "$options": "i"}},
        sort=[("created_at", -1)],
    )


def get_indexed_count() -> int:
    """Get the total number of ingested guidelines."""
    return _guidelines_col().count_documents({})


def get_all_guidelines() -> list[dict]:
    """Get all guidelines, most recent first."""
    cursor = _guidelines_col().find(
        {}, {"elements": 0}  # exclude bulky elements array
    ).sort("created_at", -1)
    results = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results
