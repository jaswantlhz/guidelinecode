"""PDF / article parsing service.

Parsing strategies (tried in order where applicable):
  1. LOCAL PDF (default):  pypdf — fast, no external service, no timeout risk.
  2. PMC XML fallback:     When a PDF URL returns HTML (cookie-blocked), fetch
                           the full article text from the NCBI EFetch XML API
                           (free, no auth key needed for open-access articles).
  3. CLOUD PDF (opt-in):  Unstructured.io Platform API — only when
                           UNSTRUCTURED_USE_API=true and UNSTRUCTURED_API_KEY
                           are set; includes a 5-min timeout with pypdf fallback.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_NCBI_EFETCH = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pmc&id={pmcid_num}&rettype=full&retmode=xml"
)
_EPMC_XML = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
_XML_HEADERS = {
    "User-Agent": "CPIC-RAG-Bot/1.0 (mailto:researcher@example.com)",
    "Accept": "application/xml,text/xml,*/*",
}

# ── Local parser (primary) ────────────────────────────────────────────────────

def _parse_with_pypdf(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Parse a PDF locally with pypdf.

    Returns a list of element-dicts compatible with the Unstructured schema:
      {"type": str, "text": str, "metadata": {"page_number": int, ...}}
    """
    try:
        import pypdf  # type: ignore
    except ImportError:
        raise ImportError("pypdf is not installed. Run: pip install pypdf")

    # Pre-check: verify magic bytes before giving file to pypdf
    with open(pdf_path, "rb") as f:
        header = f.read(8)
    if not header.lstrip()[:4] == b"%PDF":
        raise ValueError(
            f"File is not a valid PDF (header: {header!r}). "
            f"This usually means the download returned an HTML page. "
            f"Please delete '{pdf_path.name}' and try ingesting again — "
            f"the pipeline will re-download the correct PDF."
        )

    logger.info(f"Parsing '{pdf_path.name}' with pypdf (local)...")
    elements: list[dict[str, Any]] = []

    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f, strict=False)
            n_pages = len(reader.pages)
            logger.info(f"PDF has {n_pages} pages.")

            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    raw_text = page.extract_text() or ""
                except Exception as page_err:
                    logger.warning(f"Could not extract page {page_num}: {page_err}")
                    continue

                if not raw_text.strip():
                    continue

                for chunk in _split_into_chunks(raw_text, max_chars=800):
                    chunk = chunk.strip()
                    if len(chunk) < 20:
                        continue
                    elem_type = _classify_chunk(chunk)
                    elements.append({
                        "type": elem_type,
                        "text": chunk,
                        "metadata": {
                            "page_number": page_num,
                            "filename": pdf_path.name,
                        },
                    })
    except pypdf.errors.PdfStreamError as e:
        raise ValueError(
            f"pypdf could not read '{pdf_path.name}': {e}. "
            f"The file may be corrupted or is not a real PDF. "
            f"Delete it from the pdfs/ folder and try again."
        )
    except Exception as e:
        raise ValueError(f"PDF parsing failed for '{pdf_path.name}': {e}")

    logger.info(f"pypdf extracted {len(elements)} chunks from '{pdf_path.name}'")
    return elements


def _split_into_chunks(text: str, max_chars: int = 800) -> list[str]:
    """Split text on double newlines (paragraphs), then sub-split long blocks."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            # Sub-split on single newlines
            lines = para.split("\n")
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 <= max_chars:
                    current = (current + " " + line).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = line.strip()
            if current:
                chunks.append(current)
    return chunks


def _classify_chunk(text: str) -> str:
    """Heuristic element type based on text length and formatting."""
    stripped = text.strip()
    if len(stripped) < 80 and stripped[0].isupper() and not stripped.endswith("."):
        return "Title"
    if stripped.startswith(("•", "-", "–", "*")) or (len(stripped) < 200 and "\n" in stripped):
        return "ListItem"
    if any(kw in stripped.lower() for kw in ("table", "figure", "fig.")):
        return "Table"
    return "NarrativeText"


# ── Cloud parser (Unstructured Platform API, optional) ───────────────────────

def _parse_with_unstructured_api(
    pdf_path: Path,
    api_key: str,
    timeout_seconds: int = 300,
) -> list[dict[str, Any]]:
    """
    Submit a PDF to the Unstructured.io Platform API and wait for results.
    Raises RuntimeError if the job does not complete within timeout_seconds.
    """
    try:
        from unstructured_client import UnstructuredClient
        from unstructured_client.models.operations import (
            CreateJobRequest,
            DownloadJobOutputRequest,
        )
        from unstructured_client.models.shared import BodyCreateJob, InputFiles
        import json
    except ImportError:
        raise ImportError(
            "unstructured-client is not installed. "
            "Run: pip install unstructured-client"
        )

    POLL_INTERVAL = 10  # seconds
    deadline = time.monotonic() + timeout_seconds

    logger.info(
        f"Submitting '{pdf_path.name}' to Unstructured.io API "
        f"(timeout={timeout_seconds}s)..."
    )

    with UnstructuredClient(api_key_auth=api_key) as client:
        with open(pdf_path, "rb") as f:
            input_file = InputFiles(
                content=f,
                file_name=pdf_path.name,
                content_type="application/pdf",
            )
            response = client.jobs.create_job(
                request=CreateJobRequest(
                    body_create_job=BodyCreateJob(
                        request_data=json.dumps({"template_id": "hi_res_and_enrichment"}),
                        input_files=[input_file],
                    )
                )
            )

        job_id = response.job_information.id
        file_ids = response.job_information.input_file_ids
        logger.info(f"Unstructured job created: {job_id}")

        while True:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"Unstructured job {job_id} did not complete within "
                    f"{timeout_seconds}s. Using local parser instead."
                )
            status_resp = client.jobs.get_job(request={"job_id": job_id})
            status = status_resp.job_information.status

            if status in ("SCHEDULED", "IN_PROGRESS"):
                logger.info(f"Job {job_id}: {status} — polling in {POLL_INTERVAL}s...")
                time.sleep(POLL_INTERVAL)
            elif status == "COMPLETED":
                logger.info(f"Job {job_id} completed.")
                break
            else:
                raise RuntimeError(f"Unstructured job {job_id} failed: {status}")

        all_elements: list[dict[str, Any]] = []
        for file_id in file_ids:
            out = client.jobs.download_job_output(
                request=DownloadJobOutputRequest(job_id=job_id, file_id=file_id)
            )
            elems = out.any
            if isinstance(elems, list):
                all_elements.extend(elems)

    logger.info(
        f"Unstructured API extracted {len(all_elements)} elements "
        f"from '{pdf_path.name}'"
    )
    return all_elements


# ── PMC XML full-text extractor (fallback when PDF is cookie-blocked) ─────────

def parse_article_from_pmcid(pmcid: str) -> list[dict[str, Any]]:
    """
    Fetch and parse a PMC article as XML text when the PDF is unavailable.

    Uses NCBI EFetch (primary) or Europe PMC (fallback) to get full article XML,
    then extracts text from all paragraph/title elements.
    Returns elements in the same dict format as parse_pdf_with_unstructured().
    """
    pmcid = pmcid.strip()
    if not pmcid.upper().startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    pmcid_num = pmcid.replace("PMC", "").replace("pmc", "")

    xml_text = None

    # Try NCBI EFetch
    try:
        url = _NCBI_EFETCH.format(pmcid_num=pmcid_num)
        logger.info(f"Fetching PMC XML via NCBI EFetch: {url}")
        r = requests.get(url, headers=_XML_HEADERS, timeout=30)
        if r.ok and "<article" in r.text:
            xml_text = r.text
            logger.info(f"NCBI EFetch returned {len(xml_text)} chars")
    except Exception as e:
        logger.debug(f"NCBI EFetch failed: {e}")

    # Fallback: Europe PMC
    if not xml_text:
        try:
            url = _EPMC_XML.format(pmcid=pmcid)
            logger.info(f"Fetching PMC XML via Europe PMC: {url}")
            r = requests.get(url, headers=_XML_HEADERS, timeout=30)
            if r.ok and "<article" in r.text:
                xml_text = r.text
                logger.info(f"Europe PMC returned {len(xml_text)} chars")
        except Exception as e:
            logger.debug(f"Europe PMC XML failed: {e}")

    if not xml_text:
        raise ValueError(
            f"Could not retrieve full text XML for {pmcid} from NCBI or Europe PMC."
        )

    return _parse_pmc_xml(xml_text, pmcid)


def _parse_pmc_xml(xml_text: str, source_name: str) -> list[dict[str, Any]]:
    """Parse a PMC/JATS XML string into element dicts."""
    # Strip XML declaration issues and parse
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        # Try stripping BOM / encoding declaration
        clean = re.sub(r"<\?xml[^?]*\?>", "", xml_text).strip()
        try:
            root = ET.fromstring(clean)
        except ET.ParseError:
            raise ValueError(f"Failed to parse PMC XML: {e}")

    elements: list[dict[str, Any]] = []
    section_num = 0

    def _text(node) -> str:
        """Recursively get all text from an XML element."""
        parts = []
        if node.text:
            parts.append(node.text.strip())
        for child in node:
            parts.append(_text(child))
            if child.tail:
                parts.append(child.tail.strip())
        return " ".join(p for p in parts if p)

    def _walk(node, depth: int = 0):
        nonlocal section_num
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag  # strip namespace

        if tag in ("abstract", "sec"):
            section_num += 1
            for child in node:
                _walk(child, depth + 1)

        elif tag == "title":
            text = _text(node).strip()
            if len(text) > 3:
                elements.append({
                    "type": "Title",
                    "text": text,
                    "metadata": {"page_number": section_num, "filename": source_name},
                })

        elif tag == "p":
            text = _text(node).strip()
            if len(text) >= 20:
                for chunk in _split_into_chunks(text, max_chars=800):
                    chunk = chunk.strip()
                    if len(chunk) >= 20:
                        elements.append({
                            "type": "NarrativeText",
                            "text": chunk,
                            "metadata": {"page_number": section_num, "filename": source_name},
                        })

        elif tag in ("list-item", "item"):
            text = _text(node).strip()
            if len(text) >= 10:
                elements.append({
                    "type": "ListItem",
                    "text": text,
                    "metadata": {"page_number": section_num, "filename": source_name},
                })

        elif tag == "table-wrap":
            text = _text(node).strip()
            if len(text) >= 20:
                elements.append({
                    "type": "Table",
                    "text": text,
                    "metadata": {"page_number": section_num, "filename": source_name},
                })
        else:
            for child in node:
                _walk(child, depth)

    _walk(root)
    logger.info(f"PMC XML parser extracted {len(elements)} elements from '{source_name}'")
    return elements


# ── Public entry points ───────────────────────────────────────────────────────

def parse_pdf_with_unstructured(pdf_path: str | Path) -> list[dict[str, Any]]:
    """
    Parse a PDF file and return a list of element dicts.
    Uses local pypdf by default; Unstructured cloud API is opt-in.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    use_api = os.getenv("UNSTRUCTURED_USE_API", "false").lower() == "true"
    api_key = os.getenv("UNSTRUCTURED_API_KEY", "")

    if use_api and api_key:
        timeout = int(os.getenv("UNSTRUCTURED_API_TIMEOUT", "300"))
        try:
            return _parse_with_unstructured_api(pdf_path, api_key, timeout)
        except Exception as e:
            logger.warning(f"Unstructured API failed ({e}). Falling back to pypdf.")

    return _parse_with_pypdf(pdf_path)
