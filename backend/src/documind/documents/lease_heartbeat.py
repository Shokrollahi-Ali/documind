import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.documents.leases import renew_document_processing_lease


class ProcessingLeaseLostError(Exception):
    pass


async def maintain_processing_lease(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    owner_id: UUID,
    attempt_id: UUID,
    lease_seconds: int,
) -> None:
    if lease_seconds <= 0:
        raise ValueError("Processing lease duration must be positive")

    renewal_interval_seconds = lease_seconds / 3

    while True:
        await asyncio.sleep(renewal_interval_seconds)

        async with session_factory() as database_session:
            renewed = await renew_document_processing_lease(
                database_session=database_session,
                document_id=document_id,
                owner_id=owner_id,
                attempt_id=attempt_id,
                lease_seconds=lease_seconds,
            )

        if not renewed:
            raise ProcessingLeaseLostError(f"Processing lease lost for document {document_id}")
