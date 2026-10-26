from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from documind.models.document import Document, DocumentStatus


async def claim_document_processing(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    lease_seconds: int,
) -> UUID | None:
    if lease_seconds <= 0:
        raise ValueError("Processing lease duration must be positive")

    attempt_id = uuid4()

    eligible_for_processing = (Document.status == DocumentStatus.UPLOADED) | (
        (Document.status == DocumentStatus.PROCESSING)
        & (
            Document.processing_lease_expires_at.is_(None)
            | (Document.processing_lease_expires_at <= func.clock_timestamp())
        )
    )

    async with database_session.begin():
        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                eligible_for_processing,
            )
            .values(
                status=DocumentStatus.PROCESSING,
                processing_attempt_id=attempt_id,
                processing_lease_expires_at=(
                    func.clock_timestamp() + timedelta(seconds=lease_seconds)
                ),
            )
            .returning(Document.processing_attempt_id)
        )

        result = await database_session.execute(statement)
        claimed_attempt_id = result.scalar_one_or_none()

    return claimed_attempt_id


async def renew_document_processing_lease(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    attempt_id: UUID,
    lease_seconds: int,
) -> bool:
    if lease_seconds <= 0:
        raise ValueError("Processing lease duration must be positive")

    async with database_session.begin():
        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                Document.status == DocumentStatus.PROCESSING,
                Document.processing_attempt_id == attempt_id,
                Document.processing_lease_expires_at > func.clock_timestamp(),
            )
            .values(
                processing_lease_expires_at=(
                    func.clock_timestamp() + timedelta(seconds=lease_seconds)
                ),
            )
            .returning(Document.id)
        )

        result = await database_session.execute(statement)
        renewed_document_id = result.scalar_one_or_none()

    return renewed_document_id is not None


async def fail_document_processing(
    database_session: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
    attempt_id: UUID,
) -> bool:
    async with database_session.begin():
        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.owner_id == owner_id,
                Document.status == DocumentStatus.PROCESSING,
                Document.processing_attempt_id == attempt_id,
                Document.processing_lease_expires_at > func.clock_timestamp(),
            )
            .values(
                status=DocumentStatus.FAILED,
                processing_attempt_id=None,
                processing_lease_expires_at=None,
            )
            .returning(Document.id)
        )

        result = await database_session.execute(statement)
        failed_document_id = result.scalar_one_or_none()

    return failed_document_id is not None
