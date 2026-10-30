import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from documind.documents.chunking import TextChunk
from documind.documents.embedding_processing import embed_and_store_document
from documind.models.document import Document, DocumentStatus


@pytest.fixture
def session_factory() -> MagicMock:
    factory = MagicMock()
    factory.return_value = AsyncMock()
    return factory


@pytest.fixture
def document_lookup() -> Iterator[AsyncMock]:
    with patch("documind.documents.embedding_processing.get_document") as lookup:
        lookup.return_value = Document(status=DocumentStatus.CHUNKED)
        yield lookup


@pytest.fixture
def chunk_lookup() -> Iterator[AsyncMock]:
    with patch("documind.documents.embedding_processing.get_document_chunks") as lookup:
        lookup.return_value = [TextChunk(0, 1, "First"), TextChunk(1, 2, "Second")]
        yield lookup


@pytest.fixture
def save_embeddings() -> Iterator[AsyncMock]:
    with patch("documind.documents.embedding_processing.save_document_embeddings") as save:
        save.return_value = True
        yield save


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (None, False),
        (DocumentStatus.UPLOADED, False),
        (DocumentStatus.PROCESSING, False),
        (DocumentStatus.EXTRACTED, False),
        (DocumentStatus.FAILED, False),
        (DocumentStatus.READY, True),
    ],
)
def test_skips_unavailable_or_already_processed_document(
    session_factory: MagicMock,
    document_lookup: AsyncMock,
    chunk_lookup: AsyncMock,
    save_embeddings: AsyncMock,
    status: DocumentStatus | None,
    expected: bool,
) -> None:
    document_lookup.return_value = Document(status=status) if status is not None else None
    embeddings = AsyncMock()

    result = asyncio.run(embed_and_store_document(session_factory, uuid4(), uuid4(), embeddings))

    assert result is expected
    chunk_lookup.assert_not_awaited()
    embeddings.aembed_documents.assert_not_awaited()
    save_embeddings.assert_not_awaited()


@pytest.mark.parametrize("saved", [False, True])
def test_releases_read_session_before_generating_and_returns_save_result(
    session_factory: MagicMock,
    document_lookup: AsyncMock,
    chunk_lookup: AsyncMock,
    save_embeddings: AsyncMock,
    saved: bool,
) -> None:
    document_id, owner_id = uuid4(), uuid4()
    vectors = [[0.1] * 1536, [0.2] * 1536]
    embeddings = AsyncMock()
    save_embeddings.return_value = saved

    async def generate(texts: list[str]) -> list[list[float]]:
        assert texts == ["First", "Second"]
        session_factory.return_value.__aexit__.assert_awaited_once()
        assert session_factory.call_count == 1
        return vectors

    embeddings.aembed_documents.side_effect = generate
    result = asyncio.run(
        embed_and_store_document(session_factory, document_id, owner_id, embeddings)
    )

    assert result is saved
    assert session_factory.call_count == 2
    assert document_lookup.call_args.kwargs["owner_id"] == owner_id
    assert chunk_lookup.call_args.kwargs["owner_id"] == owner_id
    save_embeddings.assert_awaited_once_with(
        database_session=session_factory.return_value.__aenter__.return_value,
        document_id=document_id,
        owner_id=owner_id,
        chunks=chunk_lookup.return_value,
        vectors=vectors,
    )


def test_skips_document_without_chunks(
    session_factory: MagicMock,
    document_lookup: AsyncMock,
    chunk_lookup: AsyncMock,
    save_embeddings: AsyncMock,
) -> None:
    chunk_lookup.return_value = []
    embeddings = AsyncMock()

    assert not asyncio.run(embed_and_store_document(session_factory, uuid4(), uuid4(), embeddings))
    embeddings.aembed_documents.assert_not_awaited()
    save_embeddings.assert_not_awaited()


@pytest.mark.parametrize("failure", ["timeout", "invalid_response"])
def test_generation_failure_does_not_save(
    session_factory: MagicMock,
    document_lookup: AsyncMock,
    chunk_lookup: AsyncMock,
    save_embeddings: AsyncMock,
    failure: str,
) -> None:
    embeddings = AsyncMock()
    if failure == "timeout":
        embeddings.aembed_documents.side_effect = TimeoutError("Provider timed out")
        error: type[Exception] = TimeoutError
    else:
        embeddings.aembed_documents.return_value = []
        error = ValueError

    with pytest.raises(error):
        asyncio.run(embed_and_store_document(session_factory, uuid4(), uuid4(), embeddings))

    save_embeddings.assert_not_awaited()
    assert session_factory.call_count == 1
