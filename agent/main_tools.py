"""Agent tools — wraps each pipeline function as a LangChain tool."""

from langchain_core.tools import StructuredTool
from tools.guideline_fetching import get_guideline_pdf
from tools.link_searcher import search_pdf
from tools.pdf_retriver import download_pdf

tools = [
    StructuredTool.from_function(
        func=get_guideline_pdf,
        name="guideline_retriever",
        description="Retrieves a guideline URL from the CPIC gene-drug pairs Excel spreadsheet.",
    ),
    StructuredTool.from_function(
        func=search_pdf,
        name="link_searcher",
        description="Searches a guideline web page for .pdf download links.",
    ),
    StructuredTool.from_function(
        func=download_pdf,
        name="download_pdf",
        description="Downloads a PDF from the given URL and saves it locally.",
    ),
]