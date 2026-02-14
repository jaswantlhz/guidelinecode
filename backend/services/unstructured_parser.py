"""Unstructured.io API service — parse PDFs into structured JSON.

Adapted from Ingestion/main.py to work as a backend service.
Uses the Unstructured Platform on-demand jobs API.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from unstructured_client import UnstructuredClient
from unstructured_client.models.operations import CreateJobRequest, DownloadJobOutputRequest
from unstructured_client.models.shared import BodyCreateJob, InputFiles

from config import settings

logger = logging.getLogger(__name__)

# Job template for hi-res parsing + enrichment
JOB_TEMPLATE_ID = "hi_res_and_enrichment"
POLL_INTERVAL = 10  # seconds


def parse_pdf_with_unstructured(pdf_path: str | Path) -> list[dict[str, Any]]:
    """Parse a PDF using the Unstructured.io API.

    Submits the PDF as an on-demand job, polls for completion,
    and returns the parsed elements as a list of dicts.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    api_key = settings.UNSTRUCTURED_API_KEY
    if not api_key:
        raise ValueError("UNSTRUCTURED_API_KEY is not set in environment.")

    logger.info(f"Submitting '{pdf_path.name}' to Unstructured.io API...")

    with UnstructuredClient(api_key_auth=api_key) as client:
        # Step 1: Create the on-demand job
        with open(pdf_path, "rb") as f:
            input_file = InputFiles(
                content=f,
                file_name=pdf_path.name,
                content_type="application/pdf",
            )

            request_data = json.dumps({"template_id": JOB_TEMPLATE_ID})

            response = client.jobs.create_job(
                request=CreateJobRequest(
                    body_create_job=BodyCreateJob(
                        request_data=request_data,
                        input_files=[input_file],
                    )
                )
            )

        job_id = response.job_information.id
        job_input_file_ids = response.job_information.input_file_ids
        logger.info(f"Unstructured job created: {job_id}")

        # Step 2: Poll for completion
        while True:
            status_response = client.jobs.get_job(request={"job_id": job_id})
            status = status_response.job_information.status

            if status in ("SCHEDULED", "IN_PROGRESS"):
                logger.info(f"Job {job_id} status: {status}, polling in {POLL_INTERVAL}s...")
                time.sleep(POLL_INTERVAL)
            elif status == "COMPLETED":
                logger.info(f"Job {job_id} completed!")
                break
            else:
                raise RuntimeError(f"Unstructured job {job_id} failed with status: {status}")

        # Step 3: Download the output
        all_elements = []
        for file_id in job_input_file_ids:
            output_response = client.jobs.download_job_output(
                request=DownloadJobOutputRequest(
                    job_id=job_id,
                    file_id=file_id,
                )
            )
            elements = output_response.any
            if isinstance(elements, list):
                all_elements.extend(elements)
            else:
                logger.warning(f"Unexpected output format for file {file_id}: {type(elements)}")

        logger.info(f"Parsed {len(all_elements)} elements from '{pdf_path.name}'")
        return all_elements
