from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.api.dependencies import get_settings
from documind.api.routes import DOCUMENT_DETAIL, DOCUMENTS
from documind.api.upload_validation import validate_document_upload
from documind.core.config import Settings
from documind.db.session import get_database_session
from documind.documents.service import create_document, get_document
from documind.schemas.document import DocumentResponse
from documind.storage.s3 import get_s3_client

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    from botocore.client import BaseClient as S3Client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.post(DOCUMENTS, response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    database_session: Annotated[AsyncSession, Depends(get_database_session)],
    s3_client: Annotated[S3Client, Depends(get_s3_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:

    try:
        metadata = await validate_document_upload(file, settings)

        try:
            document = await create_document(
                database_session=database_session,
                s3_client=s3_client,
                file=file.file,
                metadata=metadata,
                bucket=settings.s3_bucket,
            )
        except (BotoCoreError, ClientError, S3UploadFailedError) as error:
            logger.exception("Document upload failed during storage")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document storage is temporarily unavailable",
            ) from error
        except SQLAlchemyError as error:
            logger.exception("Document upload failed during database persistence")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document persistence is temporarily unavailable",
            ) from error
        return DocumentResponse.model_validate(document)

    finally:
        await file.close()


@router.get(DOCUMENT_DETAIL, response_model=DocumentResponse)
async def retrieve_document(
    document_id: UUID, database_session: Annotated[AsyncSession, Depends(get_database_session)]
) -> DocumentResponse:
    try:
        document = await get_document(database_session=database_session, document_id=document_id)
    except SQLAlchemyError as error:
        logger.exception("Document retrieval failed during database lookup")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document persistence is temporarily unavailable",
        ) from error

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(document)
