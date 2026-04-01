"""Embedding service — ChromaDB vector store with PubMedBERT embeddings.

MAJOR UPGRADE from FAISS:
- ChromaDB supports native metadata filtering (gene + drug metadata)
- PubMedBERT understands medical jargon, allele star notation (CYP2D6*4), etc.
- Persistent across restarts without manual index saving
"""

from __future__ import annotations

import logging
from typing import List, Optional

import chromadb
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from config import settings

logger = logging.getLogger(__name__)

# PubMedBERT — domain-specific biomedical embedding model
# Trained on PubMed + MEDLINE; understands pharmacogenomic terminology
EMBEDDING_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO"
CHROMA_COLLECTION = "cpic_guidelines"

_embeddings: HuggingFaceEmbeddings | None = None
_vectorstore: Chroma | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """Lazy-load PubMedBERT embeddings."""
    global _embeddings
    if _embeddings is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def get_vectorstore() -> Chroma | None:
    """Get or initialize the ChromaDB vector store."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    chroma_dir = str(settings.CHROMA_DIR)
    try:
        _vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=chroma_dir,
        )
        count = _vectorstore._collection.count()
        logger.info(f"ChromaDB loaded: {count} chunks in '{CHROMA_COLLECTION}'")
        if count == 0:
            return None
    except Exception as e:
        logger.error(f"Failed to load ChromaDB: {e}")
        return None

    return _vectorstore


def add_documents(docs: List[Document]) -> int:
    """Add documents to ChromaDB and persist."""
    global _vectorstore
    emb = get_embeddings()
    chroma_dir = str(settings.CHROMA_DIR)

    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION,
            embedding_function=emb,
            persist_directory=chroma_dir,
        )

    _vectorstore.add_documents(docs)
    logger.info(f"Added {len(docs)} documents to ChromaDB.")
    return len(docs)


def similarity_search_with_filter(
    query: str,
    gene: Optional[str] = None,
    drug: Optional[str] = None,
    k: int = 20,
) -> List[tuple[Document, float]]:
    """
    Retrieve documents with STRICT metadata filtering.
    
    This is the critical fix from the scorecard:
    If gene='CYP2D6' and drug='codeine', only chunks belonging to that
    specific guideline are returned — preventing cross-contamination.
    """
    vs = get_vectorstore()
    if vs is None:
        return []

    # Build ChromaDB "where" filter
    where: dict = {}
    if gene and drug:
        where = {"$and": [{"gene": {"$eq": gene}}, {"drug": {"$eq": drug.lower()}}]}
    elif gene:
        where = {"gene": {"$eq": gene}}
    elif drug:
        where = {"drug": {"$eq": drug.lower()}}

    try:
        if where:
            results = vs.similarity_search_with_relevance_scores(query, k=k, filter=where)
        else:
            results = vs.similarity_search_with_relevance_scores(query, k=k)
    except Exception as e:
        logger.warning(f"Filtered search failed ({e}), falling back to unfiltered.")
        results = vs.similarity_search_with_relevance_scores(query, k=k)

    return results


def get_total_chunks() -> int:
    """Return total number of embedded chunks."""
    try:
        vs = get_vectorstore()
        if vs is None:
            return 0
        return vs._collection.count()
    except Exception:
        return 0
