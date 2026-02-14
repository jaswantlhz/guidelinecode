"""Metadata service — MongoDB-backed guideline metadata.

Delegates to the mongodb.py service for all storage operations.
Keeps the same function signatures for backwards compatibility.
"""

from __future__ import annotations

from services.mongodb import store_guideline, get_indexed_count, get_all_guidelines  # noqa: F401


def add_guideline(drug: str, title: str, pdf_path: str, chunks_count: int, gene: str = "") -> str:
    """Store a guideline's metadata in MongoDB and return a guideline_id."""
    return store_guideline(
        gene=gene,
        drug=drug,
        title=title,
        pdf_path=pdf_path,
        chunks_count=chunks_count,
    )
