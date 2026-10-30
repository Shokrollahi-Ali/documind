import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.core.config import Settings
from documind.db.session import create_database_engine
from documind.documents.chunking import TextChunk
from documind.documents.chunks import get_document_chunks, save_document_embeddings
from documind.documents.embedding_processing import fail_document_embedding
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk
from documind.models.user import User

pytestmark = pytest.mark.integration

CHUNKS = [TextChunk(0, 1, "First passage"), TextChunk(1, 2, "Second passage")]


@pytest.mark.parametrize("status", list(DocumentStatus))
def test_embedding_failure_changes_only_chunked_documents(
    integration_settings: Settings, status: DocumentStatus
) -> None:
    async def scenario() -> None:
        async with prepared_document(integration_settings) as (session, document):
            document.status = status
            await session.commit()
            document_id, owner_id = document.id, document.owner_id

            changed = await fail_document_embedding(session, document_id, owner_id)

            assert changed is (status == DocumentStatus.CHUNKED)
            await session.refresh(document)
            expected = DocumentStatus.FAILED if status == DocumentStatus.CHUNKED else status
            assert document.status == expected
            assert await get_document_chunks(session, document_id, owner_id) == CHUNKS

    asyncio.run(scenario())


@pytest.mark.parametrize("missing_document", [False, True])
def test_embedding_failure_requires_existing_owned_document(
    integration_settings: Settings, missing_document: bool
) -> None:
    async def scenario() -> None:
        async with prepared_document(integration_settings) as (session, document):
            document_id = uuid4() if missing_document else document.id
            owner_id = document.owner_id if missing_document else uuid4()

            assert not await fail_document_embedding(session, document_id, owner_id)

            await session.refresh(document)
            assert document.status == DocumentStatus.CHUNKED

    asyncio.run(scenario())


@asynccontextmanager
async def prepared_document(settings: Settings) -> AsyncIterator[tuple[AsyncSession, Document]]:
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as session:
                    user = User(email=f"{uuid4()}@example.com", password_hash="unused")
                    session.add(user)
                    await session.flush()
                    document = Document(
                        owner_id=user.id,
                        original_filename="embedding.pdf",
                        storage_key=f"documents/{uuid4()}.pdf",
                        content_type="application/pdf",
                        size_bytes=100,
                        status=DocumentStatus.CHUNKED,
                    )
                    session.add(document)
                    await session.flush()
                    for chunk in reversed(CHUNKS):
                        session.add(
                            DocumentChunk(
                                document_id=document.id,
                                chunk_index=chunk.chunk_index,
                                page_number=chunk.page_number,
                                text=chunk.text,
                            )
                        )
                    await session.commit()
                    yield session, document
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def test_stores_all_embeddings_and_marks_ready(integration_settings: Settings) -> None:
    async def scenario() -> None:
        async with prepared_document(integration_settings) as (session, document):
            document_id = document.id
            vectors = [[0.1] * 1536, [0.2] * 1536]
            assert await save_document_embeddings(
                session, document_id, document.owner_id, CHUNKS, vectors
            )
            session.expire_all()
            stored_document = await session.get(Document, document_id)
            assert stored_document is not None
            assert stored_document.status == DocumentStatus.READY
            stored_chunks = (
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
            ).all()
            assert len(stored_chunks) == 2
            for chunk, vector in zip(stored_chunks, vectors, strict=True):
                assert chunk.embedding is not None
                assert list(chunk.embedding) == pytest.approx(vector)

    asyncio.run(scenario())


@pytest.mark.parametrize("reason", ["owner", "missing", "status", "text", "page", "count"])
def test_rejects_inaccessible_or_changed_document(
    integration_settings: Settings, reason: str
) -> None:
    async def scenario() -> None:
        async with prepared_document(integration_settings) as (session, document):
            document_id = document.id
            owner_id = uuid4() if reason == "owner" else document.owner_id
            target_id = uuid4() if reason == "missing" else document_id
            expected_status = DocumentStatus.EXTRACTED if reason == "status" else document.status
            document.status = expected_status
            await session.commit()
            chunks = list(CHUNKS)
            if reason == "text":
                chunks[0] = TextChunk(0, 1, "Outdated text")
            elif reason == "page":
                chunks[0] = TextChunk(0, 3, "First passage")
            elif reason == "count":
                chunks = chunks[:1]

            assert not await save_document_embeddings(
                session, target_id, owner_id, chunks, [[0.1] * 1536 for _ in chunks]
            )
            await session.refresh(document)
            assert document.status == expected_status
            stored_chunks = await session.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            assert all(chunk.embedding is None for chunk in stored_chunks)

    asyncio.run(scenario())


def test_invalid_vector_rolls_back_embeddings_and_status(integration_settings: Settings) -> None:
    async def scenario() -> None:
        async with prepared_document(integration_settings) as (session, document):
            document_id = document.id
            with pytest.raises(StatementError):
                await save_document_embeddings(
                    session, document_id, document.owner_id, CHUNKS, [[0.1] * 1536, [0.2]]
                )
            await session.refresh(document)
            assert document.status == DocumentStatus.CHUNKED
            stored_chunks = await session.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            assert all(chunk.embedding is None for chunk in stored_chunks)

    asyncio.run(scenario())


@pytest.mark.parametrize("wrong_owner", [False, True])
def test_loads_chunks_in_order_only_for_owner(
    integration_settings: Settings, wrong_owner: bool
) -> None:
    async def scenario() -> None:
        async with prepared_document(integration_settings) as (session, document):
            owner_id = uuid4() if wrong_owner else document.owner_id
            chunks = await get_document_chunks(session, document.id, owner_id)
            assert chunks == ([] if wrong_owner else CHUNKS)

    asyncio.run(scenario())
