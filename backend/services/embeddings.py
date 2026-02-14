"""Embedding service — FAISS index management using sentence-transformers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from config import settings

_embeddings: HuggingFaceEmbeddings | None = None
_vectorstore: FAISS | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def get_vectorstore() -> FAISS | None:
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore
    index_path = settings.FAISS_INDEX_DIR
    if (index_path / "index.faiss").exists():
        _vectorstore = FAISS.load_local(
            str(index_path),
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
    return _vectorstore


def add_documents(docs: List[Document]) -> int:
    """Add documents to the FAISS index and persist."""
    global _vectorstore
    emb = get_embeddings()
    if _vectorstore is None:
        _vectorstore = FAISS.from_documents(docs, emb)
    else:
        _vectorstore.add_documents(docs)
    _vectorstore.save_local(str(settings.FAISS_INDEX_DIR))
    return len(docs)


def similarity_search(query: str, k: int = 5) -> List[Document]:
    vs = get_vectorstore()
    if vs is None:
        return []
    return vs.similarity_search(query, k=k)


def get_total_chunks() -> int:
    vs = get_vectorstore()
    if vs is None:
        return 0
    try:
        return vs.index.ntotal
    except Exception:
        return 0
