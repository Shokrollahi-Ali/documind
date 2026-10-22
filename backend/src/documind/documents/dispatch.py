import asyncio
import logging

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.documents.queue import publish_document_processing
from documind.models.document import Document
from documind.models.document_processing_request import DocumentProcessingRequest

logger = logging.getLogger(__name__)


async def dispatch_next_processing_request(
    database_session: AsyncSession,
    celery_app: Celery,
) -> bool:
    async with database_session.begin():
        statement = (
            select(DocumentProcessingRequest, Document.owner_id)
            .join(
                Document,
                Document.id == DocumentProcessingRequest.document_id,
            )
            .order_by(
                DocumentProcessingRequest.created_at,
                DocumentProcessingRequest.id,
            )
            .limit(1)
            .with_for_update(
                of=DocumentProcessingRequest,
                skip_locked=True,
            )
        )

        result = await database_session.execute(statement)
        pending_request = result.first()

        if pending_request is None:
            return False

        processing_request, owner_id = pending_request

        await publish_document_processing(
            celery_app=celery_app,
            document_id=processing_request.document_id,
            owner_id=owner_id,
        )

        await database_session.delete(processing_request)

    return True


async def dispatch_processing_requests(
    session_factory: async_sessionmaker[AsyncSession],
    celery_app: Celery,
    interval_seconds: float,
) -> None:
    while True:
        try:
            async with session_factory() as database_session:
                dispatched = await dispatch_next_processing_request(
                    database_session=database_session,
                    celery_app=celery_app,
                )
        except Exception:
            logger.exception("Failed to dispatch a document processing request")
            await asyncio.sleep(interval_seconds)
            continue

        if not dispatched:
            await asyncio.sleep(interval_seconds)
