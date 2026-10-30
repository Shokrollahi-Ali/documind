import asyncio
import logging
from contextlib import closing
from uuid import UUID

import httpx
from celery import Task, shared_task
from openai import APIConnectionError, InternalServerError, RateLimitError

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.chunk_processing import chunk_and_store_document
from documind.documents.embedding_processing import (
    embed_and_store_document,
    fail_document_embedding,
)
from documind.documents.embeddings import create_embeddings
from documind.documents.processing import extract_and_store_document_pages
from documind.storage.s3 import create_s3_client

logger = logging.getLogger(__name__)


async def run_document_processing(
    settings: Settings,
    document_id: UUID,
    owner_id: UUID,
) -> bool:
    engine = create_database_engine(settings)

    try:
        session_factory = create_session_factory(engine)

        with closing(create_s3_client(settings)) as s3_client:
            extracted = await extract_and_store_document_pages(
                session_factory=session_factory,
                s3_client=s3_client,
                bucket=settings.s3_bucket,
                document_id=document_id,
                owner_id=owner_id,
                lease_seconds=settings.processing_lease_seconds,
            )

        if not extracted:
            return False

        chunked = await chunk_and_store_document(
            session_factory=session_factory,
            document_id=document_id,
            owner_id=owner_id,
            chunk_size=settings.chunk_size_chars,
            chunk_overlap=settings.chunk_overlap_chars,
        )

        if not chunked:
            return False

        with httpx.Client() as http_client:
            async with httpx.AsyncClient() as http_async_client:
                embeddings = create_embeddings(
                    settings,
                    http_client=http_client,
                    http_async_client=http_async_client,
                )
                return await embed_and_store_document(
                    session_factory=session_factory,
                    document_id=document_id,
                    owner_id=owner_id,
                    embeddings=embeddings,
                )
    finally:
        await engine.dispose()


async def record_embedding_failure(
    settings: Settings,
    document_id: UUID,
    owner_id: UUID,
) -> None:
    engine = create_database_engine(settings)

    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as database_session:
            await fail_document_embedding(
                database_session=database_session,
                document_id=document_id,
                owner_id=owner_id,
            )
    finally:
        await engine.dispose()


def handle_document_failure(
    task: object,
    exc: Exception,
    task_id: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    einfo: object,
) -> None:
    document_id = kwargs.get("document_id", args[0] if args else None)
    owner_id = kwargs.get("owner_id", args[1] if len(args) > 1 else None)

    if not isinstance(document_id, str) or not isinstance(owner_id, str):
        logger.error("Cannot identify document for failed task: task_id=%s", task_id)
        return

    try:
        asyncio.run(
            record_embedding_failure(
                settings=Settings(),
                document_id=UUID(document_id),
                owner_id=UUID(owner_id),
            )
        )
    except Exception:
        logger.exception(
            "Failed to record embedding failure: task_id=%s, document_id=%s",
            task_id,
            document_id,
        )


@shared_task(
    base=Task,
    name="documind.process_document",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(APIConnectionError, InternalServerError, RateLimitError),
    retry_kwargs={"max_retries": 3},
    retry_backoff=10,
    retry_backoff_max=60,
    retry_jitter=True,
    on_failure=handle_document_failure,
)
def process_document_task(document_id: str, owner_id: str) -> bool:
    settings = Settings()

    return asyncio.run(
        run_document_processing(
            settings=settings,
            document_id=UUID(document_id),
            owner_id=UUID(owner_id),
        )
    )
