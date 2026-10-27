import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.chunk_processing import chunk_and_store_document
from documind.documents.chunking import TextChunk
from documind.documents.chunks import replace_document_chunks
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk

pytestmark = pytest.mark.integration


async def save_chunks(
    settings: Settings,
    document_id: UUID,
    owner_id: UUID,
    chunks: Sequence[TextChunk],
) -> bool:
    engine = create_database_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            return await replace_document_chunks(session, document_id, owner_id, chunks)
    finally:
        await engine.dispose()


def read_chunks(engine: Engine, document_id: UUID) -> list[TextChunk]:
    with Session(engine) as session:
        stored_chunks = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
        return [
            TextChunk(chunk.chunk_index, chunk.page_number, chunk.text) for chunk in stored_chunks
        ]


def test_saves_chunks_and_marks_document_chunked(
    integration_settings: Settings,
    integration_database_engine: Engine,
    document_session: tuple[Session, Document],
) -> None:
    session, document = document_session
    document.status = DocumentStatus.EXTRACTED
    session.commit()
    expected_chunks = [TextChunk(0, 1, "First"), TextChunk(1, 3, "Third")]

    saved = asyncio.run(
        save_chunks(integration_settings, document.id, document.owner_id, expected_chunks)
    )

    assert saved is True
    assert read_chunks(integration_database_engine, document.id) == expected_chunks
    session.refresh(document)
    assert document.status == DocumentStatus.CHUNKED

    async def retry_chunking() -> bool:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)
            return await chunk_and_store_document(
                session_factory=session_factory,
                document_id=document.id,
                owner_id=document.owner_id,
                chunk_size=1000,
                chunk_overlap=200,
            )
        finally:
            await engine.dispose()

    assert asyncio.run(retry_chunking()) is True
    assert read_chunks(integration_database_engine, document.id) == expected_chunks


@pytest.mark.parametrize("wrong_owner", [False, True])
def test_does_not_change_document_without_access_or_extracted_status(
    integration_settings: Settings,
    integration_database_engine: Engine,
    document_session: tuple[Session, Document],
    wrong_owner: bool,
) -> None:
    session, document = document_session
    if wrong_owner:
        document.status = DocumentStatus.EXTRACTED
        session.commit()
    owner_id = uuid4() if wrong_owner else document.owner_id

    saved = asyncio.run(
        save_chunks(
            integration_settings,
            document.id,
            owner_id,
            [TextChunk(0, 1, "Should not be saved")],
        )
    )

    assert saved is False
    assert read_chunks(integration_database_engine, document.id) == []


def test_invalid_chunk_rolls_back_replacement_and_status(
    integration_settings: Settings,
    integration_database_engine: Engine,
    document_session: tuple[Session, Document],
) -> None:
    session, document = document_session
    session.add(DocumentChunk(document_id=document.id, chunk_index=0, page_number=1, text="Old"))
    document.status = DocumentStatus.EXTRACTED
    session.commit()

    with pytest.raises(IntegrityError, match="ck_document_chunks_positive_page_number"):
        asyncio.run(
            save_chunks(
                integration_settings,
                document.id,
                document.owner_id,
                [TextChunk(0, 0, "Invalid")],
            )
        )

    assert read_chunks(integration_database_engine, document.id) == [TextChunk(0, 1, "Old")]
    session.refresh(document)
    assert document.status == DocumentStatus.EXTRACTED
