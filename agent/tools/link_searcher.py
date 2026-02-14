"""Search a CPIC guideline page for PDF download links."""

import requests
from html.parser import HTMLParser
from urllib.parse import urljoin


class _LinkExtractor(HTMLParser):
    """Simple HTML parser that collects all <a href> values."""

    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def search_pdf(page_url: str) -> str:
    """Fetch a guideline page and find the first .pdf link on it.

    Returns the absolute PDF URL.
    """
    resp = requests.get(page_url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (CPIC-RAG-Bot)"
    })
    resp.raise_for_status()

    parser = _LinkExtractor()
    parser.feed(resp.text)

    for href in parser.links:
        if ".pdf" in href.lower():
            return urljoin(page_url, href)

    raise ValueError(f"No PDF link found on {page_url}")