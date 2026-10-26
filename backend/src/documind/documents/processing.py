from __future__ import annotations

import asyncio
import logging
from tempfile import TemporaryFile
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from documind.documents.extraction import ExtractedPage, extract_pdf_pages
from documind.documents.lease_heartbeat import maintain_processing_lease
from documind.documents.leases import (
    claim_document_processing,
    fail_document_processing,
)
from documind.documents.pages import replace_document_pages
from documind.documents.service import get_document
from documind.models.document import DocumentStatus
from documind.storage.s3 import download_document_file

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = logging.getLogger(__name__)


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


async def extract_with_lease_renewal(
    session_factory: async_sessionmaker[AsyncSession],
    s3_client: S3Client,
    bucket: str,
    storage_key: str,
    document_id: UUID,
    owner_id: UUID,
    attempt_id: UUID,
    lease_seconds: int,
) -> list[ExtractedPage]:
    heartbeat = asyncio.create_task(
        maintain_processing_lease(
            session_factory=session_factory,
            document_id=document_id,
            owner_id=owner_id,
            attempt_id=attempt_id,
            lease_seconds=lease_seconds,
        )
    )

    try:
        pages = await extract_stored_document(
            s3_client=s3_client,
            bucket=bucket,
            storage_key=storage_key,
        )

        if heartbeat.done():
            heartbeat.result()

        return pages
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)


async def record_processing_failure(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    owner_id: UUID,
    attempt_id: UUID,
) -> None:
    try:
        async with session_factory() as database_session:
            await fail_document_processing(
                database_session=database_session,
                document_id=document_id,
                owner_id=owner_id,
                attempt_id=attempt_id,
            )
    except Exception:
        logger.exception(
            "Failed to record document processing failure: document_id=%s, attempt_id=%s",
            document_id,
            attempt_id,
        )


async def extract_and_store_document_pages(
    session_factory: async_sessionmaker[AsyncSession],
    s3_client: S3Client,
    bucket: str,
    document_id: UUID,
    owner_id: UUID,
    lease_seconds: int,
) -> bool:
    async with session_factory() as database_session:
        document = await get_document(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

        if document is None:
            return False

        if document.status in {
            DocumentStatus.EXTRACTED,
            DocumentStatus.READY,
        }:
            return True

        storage_key = document.storage_key

    async with session_factory() as database_session:
        attempt_id = await claim_document_processing(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )

    if attempt_id is None:
        return False

    try:
        pages = await extract_with_lease_renewal(
            session_factory=session_factory,
            s3_client=s3_client,
            bucket=bucket,
            storage_key=storage_key,
            document_id=document_id,
            owner_id=owner_id,
            attempt_id=attempt_id,
            lease_seconds=lease_seconds,
        )

        async with session_factory() as database_session:
            return await replace_document_pages(
                database_session=database_session,
                document_id=document_id,
                owner_id=owner_id,
                pages=pages,
                attempt_id=attempt_id,
            )
    except Exception:
        await record_processing_failure(
            session_factory=session_factory,
            document_id=document_id,
            owner_id=owner_id,
            attempt_id=attempt_id,
        )
        raise
