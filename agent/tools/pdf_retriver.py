"""Download a PDF from a URL."""

import os
import requests


def download_pdf(pdf_url: str, gene: str, drug: str, folder: str = "pdfs") -> str:
    """Download a PDF and save it locally.

    Returns the file path of the saved PDF.
    """
    os.makedirs(folder, exist_ok=True)

    resp = requests.get(pdf_url, timeout=60, headers={
        "User-Agent": "Mozilla/5.0 (CPIC-RAG-Bot)"
    })
    resp.raise_for_status()

    filename = f"{gene}_{drug}_Guideline.pdf"
    path = os.path.join(folder, filename)

    with open(path, "wb") as f:
        f.write(resp.content)

    print(f"Successfully saved to: {path}")
    return path