from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.chunking import TextChunk
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk


async def replace_document_chunks(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    chunks: Sequence[TextChunk],
) -> bool:
    if not chunks:
        raise ValueError("At least one chunk is required")

    async with database_session.begin():
        statement = (
            select(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                Document.status == DocumentStatus.EXTRACTED,
            )
            .with_for_update()
        )
        documents = await database_session.scalars(statement)
        document = documents.one_or_none()

        if document is None:
            return False

        await database_session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

        for chunk in chunks:
            database_session.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.text,
                )
            )

        document.status = DocumentStatus.CHUNKED
        await database_session.flush()

    return True
