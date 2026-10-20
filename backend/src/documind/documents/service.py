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
    owner_id: UUID,
) -> Document:
    document_id = uuid4()
    storage_key = f"documents/{document_id}.pdf"
    document = Document(
        id=document_id,
        owner_id=owner_id,
        original_filename=metadata.original_filename,
        storage_key=storage_key,
        content_type=metadata.content_type,
        size_bytes=metadata.size_bytes,
        status=DocumentStatus.UPLOADED,
    )
    commit_started = False

    try:
        await upload_document_file(
            s3_client=s3_client,
            file=file,
            bucket=bucket,
            storage_key=storage_key,
            content_type=metadata.content_type,
        )

        async with database_session.begin():
            database_session.add(document)
            await database_session.flush()
            commit_started = True

    except Exception:
        if commit_started:
            logger.exception(
                "Document commit failed; keeping S3 file because the commit outcome "
                "may be uncertain: document_id=%s, key=%s",
                document_id,
                storage_key,
            )
        else:
            await cleanup_uploaded_file(s3_client, bucket, storage_key)

        raise

    return document


async def get_document(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
) -> Document | None:
    statement = select(Document).where(
        Document.id == document_id,
        Document.owner_id == owner_id,
    )

    documents = await database_session.scalars(statement)
    return documents.one_or_none()


async def list_documents(
    database_session: AsyncSession,
    limit: int,
    offset: int,
    owner_id: UUID,
) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.owner_id == owner_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )

    documents = await database_session.scalars(statement)
    return list(documents.all())


async def delete_document(
    database_session: AsyncSession,
    s3_client: S3Client,
    document_id: UUID,
    bucket: str,
    owner_id: UUID,
) -> bool:
    async with database_session.begin():
        statement = (
            select(Document)
            .where(Document.id == document_id, Document.owner_id == owner_id)
            .with_for_update()
        )
        documents = await database_session.scalars(statement)
        document = documents.one_or_none()

        if document is None:
            return False

        storage_key = document.storage_key
        await database_session.delete(document)

    try:
        await delete_document_file(s3_client=s3_client, bucket=bucket, storage_key=storage_key)
    except Exception:
        logger.exception(
            "Failed to delete stored file after deleting document: "
            "document_id=%s, bucket=%s, key=%s",
            document_id,
            bucket,
            storage_key,
        )

    return True
