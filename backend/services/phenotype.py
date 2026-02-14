"""Phenotype service — CPIC API-based diplotype → phenotype resolution.

Uses the official CPIC REST API (api.cpicpgx.org) to look up
diplotype-to-phenotype mappings. Caches results in MongoDB for reliability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from services.mongodb import get_db

logger = logging.getLogger(__name__)

CPIC_API_BASE = "https://api.cpicpgx.org/v1"

# Retry-enabled session for the CPIC API
_session = requests.Session()
_adapter = HTTPAdapter(max_retries=Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
))
_session.mount("https://", _adapter)
_session.headers.update({"User-Agent": "CPIC-RAG-Bot/1.0"})


def _diplotype_cache():
    """Get the MongoDB collection for cached diplotype data."""
    return get_db()["diplotype_cache"]


def _fetch_and_cache(gene: str) -> list[dict]:
    """Fetch diplotype data from the CPIC API and cache in MongoDB."""
    try:
        resp = _session.get(
            f"{CPIC_API_BASE}/diplotype",
            params={"genesymbol": f"eq.{gene}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data)} diplotype entries for {gene} from CPIC API")

        if data:
            col = _diplotype_cache()
            # Clear old cache for this gene and insert fresh data
            col.delete_many({"genesymbol": gene})
            for row in data:
                row["_cached_at"] = datetime.now(timezone.utc)
            col.insert_many(data)
            logger.info(f"Cached {len(data)} entries for {gene} in MongoDB")

        return data

    except Exception as e:
        logger.warning(f"CPIC API error for {gene}: {e}. Trying MongoDB cache...")
        # Fall back to cached data
        col = _diplotype_cache()
        cached = list(col.find({"genesymbol": gene}, {"_id": 0}))
        if cached:
            logger.info(f"Using {len(cached)} cached entries for {gene}")
            return cached
        logger.error(f"No cached data for {gene} either")
        return []


def _get_diplotypes(gene: str) -> list[dict]:
    """Get diplotype data for a gene — from cache or API."""
    col = _diplotype_cache()
    cached = list(col.find({"genesymbol": gene}, {"_id": 0}))
    if cached:
        return cached
    return _fetch_and_cache(gene)


def lookup_phenotype(gene: str, diplotype: str) -> dict:
    """Look up phenotype by gene and diplotype via CPIC API + MongoDB cache."""
    rows = _get_diplotypes(gene)

    if not rows:
        return {
            "gene": gene,
            "diplotype": diplotype,
            "phenotype": "Gene not found in CPIC database",
            "activity_score": None,
            "recommendation": f"No diplotype data available for {gene}.",
        }

    # Exact match (case-insensitive)
    diplotype_lower = diplotype.lower().strip()
    match = None
    for row in rows:
        if row.get("diplotype", "").lower().strip() == diplotype_lower:
            match = row
            break

    if match is None:
        return {
            "gene": gene,
            "diplotype": diplotype,
            "phenotype": "Diplotype not found",
            "activity_score": None,
            "recommendation": f"No phenotype mapping found for {gene} {diplotype} in CPIC.",
        }

    # Parse activity score
    activity_score = None
    try:
        activity_score = float(match.get("totalactivityscore", ""))
    except (ValueError, TypeError):
        pass

    return {
        "gene": gene,
        "diplotype": diplotype,
        "phenotype": match.get("generesult", "Unknown"),
        "activity_score": activity_score,
        "recommendation": match.get("consultationtext", ""),
        "ehr_priority": match.get("ehrpriority", ""),
        "description": match.get("description", ""),
    }


def get_available_genes() -> list[str]:
    """Get the list of genes available in the CPIC diplotype database."""
    try:
        resp = _session.get(
            f"{CPIC_API_BASE}/diplotype",
            params={"select": "genesymbol", "limit": "1000"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        genes = sorted(set(row["genesymbol"] for row in data if row.get("genesymbol")))
        return genes
    except Exception as e:
        logger.error(f"CPIC API error fetching genes: {e}")
        # Fall back to cached gene names from MongoDB
        col = _diplotype_cache()
        genes = col.distinct("genesymbol")
        return sorted(genes)


def get_diplotypes_for_gene(gene: str) -> list[str]:
    """Get all unique diplotypes for a gene."""
    rows = _get_diplotypes(gene)
    diplotypes = sorted(set(row["diplotype"] for row in rows if row.get("diplotype")))
    return diplotypes
