from __future__ import annotations

from tempfile import TemporaryFile
from typing import TYPE_CHECKING

from starlette.concurrency import run_in_threadpool

from documind.documents.extraction import ExtractedPage, extract_pdf_pages
from documind.storage.s3 import download_document_file

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


async def extract_stored_document(
    s3_client: S3Client,
    bucket: str,
    storage_key: str,
) -> list[ExtractedPage]:
    with TemporaryFile(mode="w+b") as file:
        await download_document_file(
            s3_client=s3_client,
            file=file,
            bucket=bucket,
            storage_key=storage_key,
        )

        return await run_in_threadpool(extract_pdf_pages, file)
