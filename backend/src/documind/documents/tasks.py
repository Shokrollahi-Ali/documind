import asyncio
from contextlib import closing
from uuid import UUID

from celery import shared_task

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.chunk_processing import chunk_and_store_document
from documind.documents.processing import extract_and_store_document_pages
from documind.storage.s3 import create_s3_client


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

        return await chunk_and_store_document(
            session_factory=session_factory,
            document_id=document_id,
            owner_id=owner_id,
            chunk_size=settings.chunk_size_chars,
            chunk_overlap=settings.chunk_overlap_chars,
        )
    finally:
        await engine.dispose()


@shared_task(
    name="documind.process_document",
    acks_late=True,
    reject_on_worker_lost=True,
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
