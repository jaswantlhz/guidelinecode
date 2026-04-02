"""Quick smoke-test for link_searcher pipeline."""
import sys, logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
sys.path.insert(0, ".")

from agent.tools.link_searcher import search_pdf

CASES = [
    ("CYP2D6", "codeine",  "https://cpicpgx.org/guidelines/guideline-for-codeine-and-cyp2d6/"),
    ("CYP2C9", "warfarin", "https://cpicpgx.org/guidelines/guideline-for-warfarin-and-cyp2c9-and-vkorc1/"),
]

for gene, drug, url in CASES:
    print(f"\n{'='*55}\nTesting: {gene} / {drug}\n{'='*55}")
    try:
        pdf = search_pdf(page_url=url, gene=gene, drug=drug)
        print(f"[OK] PDF URL: {pdf}")
    except ValueError as e:
        print(f"[FAIL] {e}")
