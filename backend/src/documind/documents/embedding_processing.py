from uuid import UUID

from langchain_core.embeddings import Embeddings
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.documents.chunks import get_document_chunks, save_document_embeddings
from documind.documents.embeddings import generate_chunk_embeddings
from documind.documents.service import get_document
from documind.models.document import Document, DocumentStatus


async def embed_and_store_document(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    owner_id: UUID,
    embeddings: Embeddings,
) -> bool:
    async with session_factory() as database_session:
        document = await get_document(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

        if document is None:
            return False

        if document.status == DocumentStatus.READY:
            return True

        if document.status != DocumentStatus.CHUNKED:
            return False

        chunks = await get_document_chunks(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

    if not chunks:
        return False

    vectors = await generate_chunk_embeddings(chunks, embeddings)

    async with session_factory() as database_session:
        return await save_document_embeddings(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
            chunks=chunks,
            vectors=vectors,
        )


async def fail_document_embedding(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
) -> bool:
    async with database_session.begin():
        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                Document.status == DocumentStatus.CHUNKED,
            )
            .values(status=DocumentStatus.FAILED)
            .returning(Document.id)
        )

        result = await database_session.execute(statement)
        failed_document_id = result.scalar_one_or_none()

    return failed_document_id is not None
