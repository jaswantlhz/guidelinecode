"""PubMed integration service — fetch recent pharmacogenomics literature.

Uses NCBI Entrez (via Biopython) to query PubMed for recent abstracts
on a given gene-drug pair. These abstracts are embedded alongside the
CPIC PDF to provide up-to-date clinical evidence beyond static guidelines.

Setup:
    Set ENTREZ_EMAIL in your .env file. Required by NCBI.
    Set ENTREZ_API_KEY for higher rate limits (10 req/s vs 3 req/s).
"""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document

from config import settings

logger = logging.getLogger(__name__)


def fetch_pubmed_abstracts(gene: str, drug: str, max_results: int = 20) -> List[Document]:
    """
    Fetch recent PubMed abstracts for a gene-drug pair.

    Query format: ("CYP2D6" OR "CYP2D6") AND ("codeine") AND pharmacogenomics

    Returns:
        List of LangChain Document objects, one per abstract.
    """
    try:
        from Bio import Entrez
    except ImportError:
        logger.warning("biopython not installed. Run: pip install biopython")
        return []

    email = getattr(settings, "ENTREZ_EMAIL", None)
    if not email:
        logger.warning("ENTREZ_EMAIL not set in config — skipping PubMed fetch.")
        return []

    Entrez.email = email
    api_key = getattr(settings, "ENTREZ_API_KEY", None)
    if api_key:
        Entrez.api_key = api_key

    # Build the search query
    query = f'("{gene}"[Title/Abstract]) AND ("{drug}"[Title/Abstract]) AND pharmacogenomics[Title/Abstract]'
    logger.info(f"Querying PubMed: {query}")

    try:
        # Step 1: Search for PMIDs
        search_handle = Entrez.esearch(
            db="pubmed",
            term=query,
            retmax=max_results,
            sort="pub_date",  # most recent first
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()

        pmids = search_results.get("IdList", [])
        if not pmids:
            logger.info(f"No PubMed results for {gene}/{drug}.")
            return []

        logger.info(f"Found {len(pmids)} PubMed articles for {gene}/{drug}.")

        # Step 2: Fetch abstracts
        fetch_handle = Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="abstract",
            retmode="xml",
        )
        records = Entrez.read(fetch_handle)
        fetch_handle.close()

        # Step 3: Convert to LangChain Documents
        docs = []
        for record in records.get("PubmedArticle", []):
            try:
                article = record["MedlineCitation"]["Article"]
                title = str(article.get("ArticleTitle", ""))
                abstract_texts = article.get("Abstract", {}).get("AbstractText", [])

                # The abstract can be a list of sections or a single string
                if isinstance(abstract_texts, list):
                    abstract = " ".join(str(t) for t in abstract_texts)
                else:
                    abstract = str(abstract_texts)

                if not abstract.strip() or len(abstract) < 50:
                    continue

                pmid = str(record["MedlineCitation"]["PMID"])

                docs.append(Document(
                    page_content=f"Title: {title}\n\nAbstract: {abstract}",
                    metadata={
                        "source": "pubmed",
                        "pmid": pmid,
                        "title": title,
                        "gene": gene,
                        "drug": drug.lower(),
                        "element_type": "PubMedAbstract",
                        "page": 0,
                    },
                ))
            except (KeyError, IndexError) as e:
                logger.debug(f"Skipping malformed PubMed record: {e}")
                continue

        logger.info(f"Converted {len(docs)} PubMed abstracts to documents.")
        return docs

    except Exception as e:
        logger.error(f"PubMed fetch failed for {gene}/{drug}: {e}")
        return []
