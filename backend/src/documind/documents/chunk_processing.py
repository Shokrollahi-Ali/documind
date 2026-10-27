from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from documind.documents.chunking import split_document_pages
from documind.documents.chunks import replace_document_chunks
from documind.documents.pages import get_document_pages
from documind.documents.service import get_document
from documind.models.document import DocumentStatus


async def chunk_and_store_document(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    owner_id: UUID,
    chunk_size: int,
    chunk_overlap: int,
) -> bool:
    async with session_factory() as database_session:
        document = await get_document(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

        if document is None:
            return False

        if document.status in {DocumentStatus.CHUNKED, DocumentStatus.READY}:
            return True

        if document.status != DocumentStatus.EXTRACTED:
            return False

        pages = await get_document_pages(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

    if not pages:
        return False

    chunks = await run_in_threadpool(
        split_document_pages,
        pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    async with session_factory() as database_session:
        return await replace_document_chunks(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
            chunks=chunks,
        )
