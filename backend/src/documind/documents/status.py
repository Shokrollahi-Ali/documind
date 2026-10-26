from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from documind.models.document import Document, DocumentStatus


async def transition_document_status(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    expected_status: DocumentStatus,
    new_status: DocumentStatus,
) -> bool:
    async with database_session.begin():
        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                Document.status == expected_status,
            )
            .values(status=new_status)
            .returning(Document.id)
        )

        result = await database_session.execute(statement)
        updated_document_id = result.scalar_one_or_none()

    return updated_document_id is not None
