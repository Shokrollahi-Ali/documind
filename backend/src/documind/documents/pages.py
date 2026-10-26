from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.extraction import ExtractedPage
from documind.models.document import Document, DocumentStatus
from documind.models.document_page import DocumentPage


async def replace_document_pages(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    pages: Sequence[ExtractedPage],
    attempt_id: UUID,
) -> bool:
    if not pages:
        raise ValueError("At least one extracted page is required")

    async with database_session.begin():
        statement = (
            select(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                Document.status == DocumentStatus.PROCESSING,
                Document.processing_attempt_id == attempt_id,
                Document.processing_lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        documents = await database_session.scalars(statement)
        document = documents.one_or_none()

        if document is None:
            return False

        await database_session.execute(
            delete(DocumentPage).where(DocumentPage.document_id == document_id)
        )

        for page in pages:
            database_session.add(
                DocumentPage(
                    document_id=document_id,
                    page_number=page.page_number,
                    text=page.text,
                )
            )

        document.status = DocumentStatus.EXTRACTED
        document.processing_attempt_id = None
        document.processing_lease_expires_at = None

        await database_session.flush()

    return True
