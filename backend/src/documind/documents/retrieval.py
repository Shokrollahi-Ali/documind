from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.embeddings import validate_embedding
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: UUID
    chunk_index: int
    page_number: int
    text: str
    cosine_distance: float


async def retrieve_document_chunks(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    query_embedding: Sequence[float],
    *,
    limit: int,
) -> list[RetrievedChunk]:
    validate_embedding(query_embedding)

    if not any(query_embedding):
        raise ValueError("Query embedding must not be a zero vector")

    if limit <= 0:
        raise ValueError("Retrieval limit must be positive")

    distance = DocumentChunk.embedding.cosine_distance(list(query_embedding))

    statement = (
        select(DocumentChunk, distance.label("cosine_distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            Document.id == document_id,
            Document.owner_id == owner_id,
            Document.status == DocumentStatus.READY,
            DocumentChunk.embedding.is_not(None),
            func.vector_norm(DocumentChunk.embedding) > 0,
        )
        .order_by(distance, DocumentChunk.chunk_index)
        .limit(limit)
    )

    result = await database_session.execute(statement)

    return [
        RetrievedChunk(
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            text=chunk.text,
            cosine_distance=float(cosine_distance),
        )
        for chunk, cosine_distance in result
    ]
