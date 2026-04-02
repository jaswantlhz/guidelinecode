"""Search for a CPIC guideline PDF using a robust dynamic multi-strategy pipeline.

Strategy chain (NO hardcoded URLs):
  1. CPIC REST API + publication walk → collect ALL PMIDs for the guideline
  2. For each PMID (most-recent first):
       a. NCBI idconv → PMCID + DOI
       b. PMC PDF URL (pmc.ncbi.nlm.nih.gov/articles/<PMCID>/pdf/)
       c. Europe PMC fullTextUrlList
       d. Unpaywall (DOI-based)
       e. Semantic Scholar openAccessPdf
  3. HTML scrape of the Excel URL with one-level CPIC sub-page follow

Key design principle:
  URL discovery is LENIENT — any 200-OK URL is returned and the downloader
  (pdf_retriver.py) is responsible for validating actual PDF bytes.
  This avoids false-rejects from redirect chains and bot-detection pages
  that return HTML on HEAD/small-GET but serve real PDFs for full downloads.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

_CPIC_API     = "https://api.cpicpgx.org/v1"
_NCBI_IDCONV  = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
_PMC_PDF_BASE = "https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/"
_EPMC_SEARCH  = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_SS_PAPER     = "https://api.semanticscholar.org/graph/v1/paper/PMID:{pmid}"
_UNPAYWALL    = "https://api.unpaywall.org/v2/{doi}"
_BOT_EMAIL    = "researcher@example.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
}
_TIMEOUT = 30


# ── URL reachability check (lenient — just checks HTTP 200) ──────────────────

def _url_ok(url: str) -> bool:
    """Return True if the URL responds with HTTP 2xx. Does NOT validate bytes."""
    try:
        r = requests.head(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        return r.ok
    except Exception:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=15,
                             allow_redirects=True, stream=True)
            r.close()
            return r.ok
        except Exception:
            return False


def _first_ok(*urls: str) -> Optional[str]:
    """Return the first URL in the list that responds OK, or None."""
    for url in urls:
        if url and _url_ok(url):
            logger.info(f"Reachable PDF URL: {url}")
            return url
    return None


# ── HTML link extractor ───────────────────────────────────────────────────────

class _LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def _get_links(url: str) -> list[str]:
    try:
        r = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
        p = _LinkExtractor()
        p.feed(r.text)
        return [urljoin(url, h) for h in p.links]
    except Exception as e:
        logger.debug(f"_get_links({url}): {e}")
        return []


# ── NCBI idconv: PMID → (PMCID, DOI) ─────────────────────────────────────────

def _pmid_to_ids(pmid: int) -> tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(
            _NCBI_IDCONV,
            params={"ids": str(pmid), "format": "json",
                    "tool": "cpic-rag-bot", "email": _BOT_EMAIL},
            timeout=_TIMEOUT, headers=_HEADERS,
        )
        r.raise_for_status()
        recs = r.json().get("records", [])
        if recs:
            return recs[0].get("pmcid"), recs[0].get("doi")
    except Exception as e:
        logger.debug(f"NCBI idconv pmid={pmid}: {e}")
    return None, None


# ── Source A: PMC PDF ─────────────────────────────────────────────────────────

def _pdf_from_pmcid(pmcid: str) -> Optional[str]:
    url = _PMC_PDF_BASE.format(pmcid=pmcid)
    return _first_ok(url)


# ── Source B: Europe PMC full-text links ──────────────────────────────────────

def _pdf_from_epmc(pmid: int) -> Optional[str]:
    try:
        r = requests.get(
            _EPMC_SEARCH,
            params={
                "query": f"EXT_ID:{pmid}",
                "src": "med",
                "resultType": "core",
                "format": "json",
            },
            timeout=_TIMEOUT, headers=_HEADERS,
        )
        r.raise_for_status()
        results = r.json().get("resultList", {}).get("result", [])
        for res in results:
            for link in res.get("fullTextUrlList", {}).get("fullTextUrl", []):
                url = link.get("url", "")
                avail = link.get("availability", "")
                doc_style = link.get("documentStyle", "")
                if doc_style == "pdf" and avail in ("Open access", "OA"):
                    if _first_ok(url):
                        return url
            # Also accept HTML full-text links from OA sources
            for link in res.get("fullTextUrlList", {}).get("fullTextUrl", []):
                url = link.get("url", "")
                avail = link.get("availability", "")
                if avail in ("Open access", "OA") and url:
                    if _first_ok(url):
                        return url
    except Exception as e:
        logger.debug(f"Europe PMC pmid={pmid}: {e}")
    return None


# ── Source C: Unpaywall ───────────────────────────────────────────────────────

def _pdf_from_doi(doi: str) -> Optional[str]:
    try:
        r = requests.get(
            _UNPAYWALL.format(doi=doi),
            params={"email": _BOT_EMAIL},
            timeout=_TIMEOUT, headers=_HEADERS,
        )
        r.raise_for_status()
        data = r.json()
        best = data.get("best_oa_location") or {}
        url = best.get("url_for_pdf") or best.get("url_for_landing_page")
        if url and _first_ok(url):
            return url
        for loc in data.get("oa_locations", []):
            url = loc.get("url_for_pdf")
            if url and _first_ok(url):
                return url
    except Exception as e:
        logger.debug(f"Unpaywall doi={doi}: {e}")
    return None


# ── Source D: Semantic Scholar ────────────────────────────────────────────────

def _pdf_from_semantic_scholar(pmid: int) -> Optional[str]:
    try:
        r = requests.get(
            _SS_PAPER.format(pmid=pmid),
            params={"fields": "openAccessPdf,title"},
            timeout=_TIMEOUT,
            headers={**_HEADERS, "User-Agent": "CPIC-RAG-Bot/1.0"},
        )
        if r.status_code == 429:
            logger.debug("Semantic Scholar rate-limited")
            return None
        r.raise_for_status()
        data = r.json()
        oa = data.get("openAccessPdf") or {}
        url = oa.get("url")
        if url and _first_ok(url):
            return url
    except Exception as e:
        logger.debug(f"Semantic Scholar pmid={pmid}: {e}")
    return None


# ── Resolve a single PMID → PDF URL ──────────────────────────────────────────

def _resolve_pmid(pmid: int) -> Optional[str]:
    """Try all PDF sources for a PMID. Returns first working URL or None."""
    pmcid, doi = _pmid_to_ids(pmid)
    logger.info(f"NCBI idconv: pmid={pmid} → pmcid={pmcid}, doi={doi}")

    # A: PMC PDF
    if pmcid:
        pdf = _pdf_from_pmcid(pmcid)
        if pdf:
            return pdf

    # B: Europe PMC
    pdf = _pdf_from_epmc(pmid)
    if pdf:
        return pdf

    # C: Unpaywall (DOI-based)
    if doi:
        pdf = _pdf_from_doi(doi)
        if pdf:
            return pdf

    # D: Semantic Scholar
    pdf = _pdf_from_semantic_scholar(pmid)
    if pdf:
        return pdf

    return None


# ── CPIC API → ALL PMIDs for a guideline ─────────────────────────────────────

def _cpic_all_pmids(gene: str, drug: str) -> list[int]:
    """
    Return all PMIDs for the best-matching CPIC guideline (most recent first).
    This gives more chances to find an OA version when the primary paper
    is paywalled.
    """
    try:
        r = requests.get(f"{_CPIC_API}/guideline", timeout=_TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
        guidelines = r.json()
    except Exception as e:
        logger.warning(f"CPIC guideline list: {e}")
        return []

    gene_up  = gene.upper()
    drug_low = drug.lower()

    # Prefer gene+drug name match, fall back to gene-only
    best = None
    for gl in guidelines:
        if gene_up not in [g.upper() for g in gl.get("genes", [])]:
            continue
        if drug_low in (gl.get("name") or "").lower():
            best = gl
            break
    if best is None:
        for gl in guidelines:
            if gene_up in [g.upper() for g in gl.get("genes", [])]:
                best = gl
                logger.info(f"CPIC gene-only match: '{gl.get('name')}'")
                break

    if not best:
        logger.warning(f"No CPIC guideline found for {gene}")
        return []

    gl_id = best["id"]
    logger.info(f"CPIC guideline '{best.get('name')}' (id={gl_id})")

    # Walk ALL publications, collect PMIDs for this guideline
    pmids: list[int] = []
    try:
        r = requests.get(f"{_CPIC_API}/publication", timeout=60, headers=_HEADERS)
        if r.ok:
            for pub in r.json():
                if pub.get("guidelineid") == gl_id and pub.get("pmid"):
                    pmids.append(int(pub["pmid"]))
    except Exception as e:
        logger.debug(f"CPIC pub walk: {e}")

    # Sort descending (most recent PMID = highest number = most likely OA)
    pmids.sort(reverse=True)
    logger.info(f"Found {len(pmids)} PMID(s) for guideline {gl_id}: {pmids}")
    return pmids


# ── HTML scrape fallback ──────────────────────────────────────────────────────

def _html_pdf(page_url: str, depth: int = 0) -> Optional[str]:
    links = _get_links(page_url)
    for href in links:
        if ".pdf" in href.lower() and _url_ok(href):
            logger.info(f"HTML scrape found PDF link: {href}")
            return href
    if depth > 0:
        return None
    cpic_re = re.compile(r"cpicpgx\.org/guidelines?/[^\"'#?\s]+", re.I)
    for href in links:
        if cpic_re.search(href) and href.rstrip("/") != page_url.rstrip("/"):
            logger.info(f"Following sub-page: {href}")
            result = _html_pdf(href, depth=1)
            if result:
                return result
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def search_pdf(page_url: str, gene: str = "", drug: str = "") -> str:
    """
    Find a reachable CPIC guideline PDF URL for a given gene/drug pair.

    URL reachability is checked leniently (HTTP 200 is enough).
    Actual PDF byte-validation happens in pdf_retriver.download_pdf().

    Returns str (PDF URL) or raises ValueError.
    """
    # Strategy 1: CPIC API → all PMIDs → multi-source PDF search
    if gene:
        logger.info(f"[S1] CPIC API: gene={gene} drug={drug}")
        pmids = _cpic_all_pmids(gene=gene, drug=drug)
        for pmid in pmids:
            pdf = _resolve_pmid(pmid)
            if pdf:
                return pdf
        if pmids:
            logger.warning(
                f"Tried {len(pmids)} PMID(s) — none had an accessible PDF. "
                f"Falling back to HTML scrape."
            )

    # Strategy 2: HTML scrape of the Excel page URL
    logger.info(f"[S2] HTML scrape: {page_url}")
    pdf = _html_pdf(page_url, depth=0)
    if pdf:
        return pdf

    raise ValueError(
        f"No accessible PDF found for {gene}/{drug}. "
        f"Tried CPIC API ({gene} publications) via PMC, Europe PMC, "
        f"Unpaywall, Semantic Scholar, and HTML scraping of {page_url}. "
        f"The guideline may be fully paywalled — check if a PDF exists "
        f"at https://cpicpgx.org/guidelines/ and upload it manually."
    )