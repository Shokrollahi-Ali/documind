import asyncio
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.retrieval import RetrievedChunk, retrieve_document_chunks
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk
from documind.models.user import User

pytestmark = pytest.mark.integration


def vector(first: float, second: float = 0) -> list[float]:
    return [first, second] + [0.0] * 1534


@pytest.fixture
def searchable_document(
    document_session: tuple[Session, Document],
) -> Iterator[tuple[Session, Document]]:
    session, document = document_session
    owner_id = document.owner_id
    try:
        document.status = DocumentStatus.READY
        embeddings = [vector(-1), vector(0, 1), vector(1), vector(1), None, vector(0)]
        for index in reversed(range(len(embeddings))):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    page_number=index + 1,
                    text=f"Passage {index}",
                    embedding=embeddings[index],
                )
            )
        other_document = Document(
            owner_id=owner_id,
            original_filename="other.pdf",
            storage_key=f"documents/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=100,
            status=DocumentStatus.READY,
        )
        session.add(other_document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=other_document.id,
                chunk_index=0,
                page_number=1,
                text="Another document must not appear",
                embedding=vector(1),
            )
        )
        session.commit()
        yield session, document
    finally:
        session.rollback()
        session.execute(delete(Document).where(Document.owner_id == owner_id))
        session.execute(delete(User).where(User.id == owner_id))
        session.commit()


async def search(
    settings: Settings, document_id: UUID, owner_id: UUID, limit: int
) -> list[RetrievedChunk]:
    engine = create_database_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            return await retrieve_document_chunks(
                session, document_id, owner_id, vector(1), limit=limit
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("limit", [1, 3, 10])
def test_ranks_only_valid_chunks_with_deterministic_ties(
    integration_settings: Settings,
    searchable_document: tuple[Session, Document],
    limit: int,
) -> None:
    _, document = searchable_document
    results = asyncio.run(search(integration_settings, document.id, document.owner_id, limit))

    assert [result.chunk_index for result in results] == [2, 3, 1, 0][:limit]
    assert [result.cosine_distance for result in results] == pytest.approx([0, 0, 1, 2][:limit])
    for result in results:
        assert result.document_id == document.id
        assert result.page_number == result.chunk_index + 1
        assert result.text == f"Passage {result.chunk_index}"


@pytest.mark.parametrize("missing_document", [False, True])
def test_does_not_return_chunks_without_document_access(
    integration_settings: Settings,
    searchable_document: tuple[Session, Document],
    missing_document: bool,
) -> None:
    _, document = searchable_document
    document_id = uuid4() if missing_document else document.id
    owner_id = document.owner_id if missing_document else uuid4()

    assert asyncio.run(search(integration_settings, document_id, owner_id, 10)) == []


@pytest.mark.parametrize(
    "status", [status for status in DocumentStatus if status != DocumentStatus.READY]
)
def test_does_not_search_unready_documents(
    integration_settings: Settings,
    searchable_document: tuple[Session, Document],
    status: DocumentStatus,
) -> None:
    session, document = searchable_document
    document.status = status
    session.commit()

    assert asyncio.run(search(integration_settings, document.id, document.owner_id, 10)) == []
