from __future__ import annotations

from tempfile import TemporaryFile
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from documind.documents.extraction import ExtractedPage, extract_pdf_pages
from documind.documents.pages import replace_document_pages
from documind.documents.service import get_document
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


async def extract_and_store_document_pages(
    session_factory: async_sessionmaker[AsyncSession],
    s3_client: S3Client,
    bucket: str,
    document_id: UUID,
    owner_id: UUID,
) -> bool:
    async with session_factory() as database_session:
        document = await get_document(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

        if document is None:
            return False

        storage_key = document.storage_key

    pages = await extract_stored_document(
        s3_client=s3_client,
        bucket=bucket,
        storage_key=storage_key,
    )

    async with session_factory() as database_session:
        return await replace_document_pages(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
            pages=pages,
        )
