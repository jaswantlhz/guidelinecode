"""Download a PDF from a URL with validation and retry logic."""

import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _is_pdf_bytes(data: bytes) -> bool:
    """Return True if the bytes start with the PDF magic header."""
    return data.lstrip()[:4] == b"%PDF"


def download_pdf(
    pdf_url: str,
    gene: str,
    drug: str,
    folder: str = "pdfs",
) -> str:
    """
    Download a PDF from pdf_url and save it locally.

    Validates that the downloaded content is a real PDF (magic bytes check).
    If the server returns HTML (e.g. a login/landing page), raises ValueError
    with the first 120 bytes so the caller can try a different URL.

    Returns the local file path on success.
    """
    os.makedirs(folder, exist_ok=True)
    filename = f"{gene}_{drug}_Guideline.pdf"
    path = os.path.join(folder, filename)

    logger.info(f"Downloading PDF: {pdf_url}")

    # Stream download so we can peek at headers early
    with requests.get(
        pdf_url,
        headers=_HEADERS,
        timeout=90,
        allow_redirects=True,
        stream=True,
    ) as resp:
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            # Server explicitly announced HTML — don't bother reading the body
            raise ValueError(
                f"Server returned HTML instead of PDF for {pdf_url!r} "
                f"(Content-Type: {content_type}). "
                f"The URL may require browser cookies or login."
            )

        # Write to a temp path first so we don't leave a corrupt file on failure
        tmp_path = path + ".tmp"
        first_chunk: Optional[bytes] = None

        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    if first_chunk is None:
                        first_chunk = chunk
                    f.write(chunk)

    # Validate that we got real PDF bytes
    if first_chunk is None or not _is_pdf_bytes(first_chunk):
        header_preview = (first_chunk or b"")[:120]
        os.remove(tmp_path)
        raise ValueError(
            f"Downloaded content is not a valid PDF from {pdf_url!r}. "
            f"First bytes: {header_preview!r}. "
            f"The server may have returned an HTML landing page."
        )

    # Rename temp → final
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp_path, path)

    size_kb = Path(path).stat().st_size // 1024
    logger.info(f"Saved PDF ({size_kb} KB): {path}")
    print(f"Successfully saved to: {path} ({size_kb} KB)")
    return path