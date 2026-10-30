from uuid import UUID

from langchain_core.embeddings import Embeddings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.documents.embeddings import generate_query_embedding
from documind.documents.retrieval import RetrievedChunk, retrieve_document_chunks
from documind.documents.service import get_document
from documind.models.document import DocumentStatus


class DocumentNotFoundError(Exception):
    pass


class DocumentNotReadyError(Exception):
    pass


async def search_document(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    owner_id: UUID,
    query: str,
    embeddings: Embeddings,
    *,
    limit: int,
) -> list[RetrievedChunk]:
    if limit <= 0:
        raise ValueError("Search limit must be positive")

    async with session_factory() as database_session:
        document = await get_document(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
        )

        if document is None:
            raise DocumentNotFoundError("Document not found")

        if document.status != DocumentStatus.READY:
            raise DocumentNotReadyError("Document is not ready for search")

    query_embedding = await generate_query_embedding(query, embeddings)

    async with session_factory() as database_session:
        return await retrieve_document_chunks(
            database_session=database_session,
            document_id=document_id,
            owner_id=owner_id,
            query_embedding=query_embedding,
            limit=limit,
        )
