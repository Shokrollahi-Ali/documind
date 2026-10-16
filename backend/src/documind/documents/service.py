from __future__ import annotations

import logging
from typing import TYPE_CHECKING, BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documind.models.document import Document, DocumentStatus
from documind.schemas.document_upload import DocumentUploadMetadata
from documind.storage.s3 import delete_document_file, upload_document_file

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = logging.getLogger(__name__)


async def cleanup_uploaded_file(s3_client: S3Client, bucket: str, storage_key: str) -> None:
    try:
        await delete_document_file(
            s3_client=s3_client,
            bucket=bucket,
            storage_key=storage_key,
        )
    except Exception:
        logger.exception(
            "Failed to delete uploaded file during cleanup: bucket=%s, key=%s",
            bucket,
            storage_key,
        )


async def create_document(
    database_session: AsyncSession,
    s3_client: S3Client,
    file: BinaryIO,
    metadata: DocumentUploadMetadata,
    bucket: str,
) -> Document:
    document_id = uuid4()
    storage_key = f"documents/{document_id}.pdf"
    document = Document(
        id=document_id,
        original_filename=metadata.original_filename,
        storage_key=storage_key,
        content_type=metadata.content_type,
        size_bytes=metadata.size_bytes,
        status=DocumentStatus.UPLOADED,
    )
    upload_attempted = False
    commit_started = False

    try:
        async with database_session.begin():
            database_session.add(document)
            await database_session.flush()

            upload_attempted = True
            await upload_document_file(
                s3_client=s3_client,
                file=file,
                bucket=bucket,
                storage_key=storage_key,
                content_type=metadata.content_type,
            )
            commit_started = True

    except Exception:
        if commit_started:
            logger.exception(
                "Document commit failed; keeping S3 file because the commit outcome "
                "may be uncertain: document_id=%s, key=%s",
                document_id,
                storage_key,
            )
        elif upload_attempted:
            await cleanup_uploaded_file(s3_client, bucket, storage_key)

        raise

    return document


async def get_document(database_session: AsyncSession, document_id: UUID) -> Document | None:
    return await database_session.get(Document, document_id)


async def list_documents(database_session: AsyncSession, limit: int, offset: int) -> list[Document]:
    statement = (
        select(Document)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )

    documents = await database_session.scalars(statement)
    return list(documents.all())


async def delete_document(
    database_session: AsyncSession, s3_client: S3Client, document_id: UUID, bucket: str
) -> bool:
    async with database_session.begin():
        document = await database_session.get(
            Document,
            document_id,
            with_for_update=True,
        )

        if document is None:
            return False

        await delete_document_file(
            s3_client=s3_client, bucket=bucket, storage_key=document.storage_key
        )

        await database_session.delete(document)

    return True
