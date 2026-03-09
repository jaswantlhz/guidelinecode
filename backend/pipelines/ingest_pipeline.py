"""ZenML pipeline for CPIC Guideline Ingestion.

Transforms the previous FastAPI-based ingestion into a ZenML pipeline that
logs metrics and artifacts using MLflow.
"""

from typing import Dict, Any, Tuple
import os
from pathlib import Path
import logging

from zenml import step, pipeline
import mlflow

from config import settings
from services.metadata import add_guideline
from services.mongodb import get_guideline, store_guideline
from services.unstructured_parser import parse_pdf_with_unstructured
from services.embeddings import add_documents
from services.ingestion import _fetch_guideline_pdf, _find_pdf, _elements_to_documents

logger = logging.getLogger(__name__)

# --- ZenML Steps ---

@step
def check_existing_guideline_step(gene: str, drug: str) -> bool:
    """Check if the guideline is already ingested in MongoDB."""
    existing = get_guideline(gene=gene, drug=drug)
    if existing:
        logger.info(f"Guideline for {gene}/{drug} already exists.")
        return True
    return False

@step
def fetch_or_find_pdf_step(gene: str, drug: str, skip: bool) -> str:
    """Finds an existing PDF or fetches it using the agent tools."""
    if skip:
        return ""
        
    pdf_path = _find_pdf(drug)
    if pdf_path is None:
        logger.info(f"No existing PDF for {drug}. Running agent pipeline...")
        pdf_path = _fetch_guideline_pdf(gene=gene, drug=drug)
        
    if pdf_path is None:
        raise ValueError(f"Could not find or fetch a guideline PDF for '{gene}/{drug}'.")
        
    return str(pdf_path)

@step
def parse_pdf_step(pdf_path_str: str) -> list:
    """Parses the PDF using Unstructured.io API."""
    if not pdf_path_str:
        return []
        
    pdf_path = Path(pdf_path_str)
    logger.info(f"Parsing '{pdf_path.name}' with Unstructured.io API...")
    
    # MLflow tracking
    mlflow.log_param("pdf_filename", pdf_path.name)
    
    elements = parse_pdf_with_unstructured(pdf_path)
    if not elements:
        raise ValueError(f"Unstructured.io returned no elements for '{pdf_path.name}'.")
        
    mlflow.log_metric("unstructured_elements_count", len(elements))
    return elements

@step
def process_and_store_step(
    gene: str, 
    drug: str, 
    pdf_path_str: str, 
    elements: list
) -> str:
    """Converts elements to LangChain documents, stores in DB, and chunks into FAISS."""
    if not elements or not pdf_path_str:
        return ""
        
    pdf_path = Path(pdf_path_str)
    
    docs = _elements_to_documents(elements, gene=gene, drug=drug)
    if not docs:
        raise ValueError(f"No meaningful text extracted from '{pdf_path.name}'.")
        
    # Store in MongoDB
    guideline_id = store_guideline(
        gene=gene,
        drug=drug,
        title=pdf_path.stem,
        pdf_path=str(pdf_path),
        chunks_count=len(docs),
        unstructured_elements=elements,
    )
    
    # Embed in FAISS
    chunks_added = add_documents(docs)
    
    # MLflow tracking
    mlflow.log_metric("chunks_embedded", chunks_added)
    mlflow.log_param("guideline_id", str(guideline_id))
    
    return str(guideline_id)


# --- ZenML Pipeline ---

from zenml.client import Client

# Ensure MLflow is active for this pipeline
@pipeline(enable_cache=False)
def cpic_ingestion_pipeline(gene: str = "CYP2C19", drug: str = "Clopidogrel"):
    """ZenML pipeline to ingest a CPIC guideline."""
    
    # Log global pipeline params to MLflow
    mlflow.log_param("gene", gene)
    mlflow.log_param("drug", drug)
    
    skip = check_existing_guideline_step(gene=gene, drug=drug)
    pdf_path = fetch_or_find_pdf_step(gene=gene, drug=drug, skip=skip)
    elements = parse_pdf_step(pdf_path_str=pdf_path)
    guideline_id = process_and_store_step(
        gene=gene, 
        drug=drug, 
        pdf_path_str=pdf_path, 
        elements=elements
    )
    
    return guideline_id
