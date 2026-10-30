import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from documind.core.config import Settings
from documind.documents.chunking import TextChunk
from documind.documents.embeddings import (
    create_embeddings,
    generate_chunk_embeddings,
    generate_query_embedding,
)


def test_embeds_trimmed_query() -> None:
    embeddings = AsyncMock()
    vector = [0.1] * 1536
    embeddings.aembed_query.return_value = vector

    result = asyncio.run(generate_query_embedding("  What is Documind?\n", embeddings))

    assert result == vector
    embeddings.aembed_query.assert_awaited_once_with("What is Documind?")
    embeddings.aembed_documents.assert_not_awaited()


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_rejects_blank_query_before_calling_provider(query: str) -> None:
    embeddings = AsyncMock()

    with pytest.raises(ValueError, match="Query must not be empty"):
        asyncio.run(generate_query_embedding(query, embeddings))

    embeddings.aembed_query.assert_not_awaited()


@pytest.mark.parametrize(
    ("vector", "message"),
    [
        ([], "Each embedding must have 1536 dimensions"),
        ([0.1] * 1535, "Each embedding must have 1536 dimensions"),
        ([0.1] * 1537, "Each embedding must have 1536 dimensions"),
        ([float("nan")] + [0.1] * 1535, "Embedding values must be finite"),
        ([float("inf")] + [0.1] * 1535, "Embedding values must be finite"),
        ([float("-inf")] + [0.1] * 1535, "Embedding values must be finite"),
    ],
)
def test_rejects_invalid_query_embedding(vector: list[float], message: str) -> None:
    embeddings = AsyncMock()
    embeddings.aembed_query.return_value = vector

    with pytest.raises(ValueError, match=message):
        asyncio.run(generate_query_embedding("What is Documind?", embeddings))


def test_propagates_query_provider_failure() -> None:
    embeddings = AsyncMock()
    embeddings.aembed_query.side_effect = TimeoutError("Provider timed out")

    with pytest.raises(TimeoutError, match="Provider timed out"):
        asyncio.run(generate_query_embedding("What is Documind?", embeddings))


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_rejects_missing_or_blank_api_key(api_key: str | None) -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key=SecretStr(api_key) if api_key is not None else None,
    )

    with patch("documind.documents.embeddings.OpenAIEmbeddings") as client_factory:
        with pytest.raises(ValueError, match="DOCUMIND_OPENAI_API_KEY must be set"):
            create_embeddings(
                settings,
                http_client=MagicMock(spec=httpx.Client),
                http_async_client=AsyncMock(spec=httpx.AsyncClient),
            )

    client_factory.assert_not_called()


def test_factory_uses_managed_http_clients() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key=SecretStr("test-key"),
        embedding_request_timeout_seconds=12.5,
    )

    async def scenario() -> None:
        with httpx.Client() as http_client:
            async with httpx.AsyncClient() as http_async_client:
                embeddings = create_embeddings(
                    settings,
                    http_client=http_client,
                    http_async_client=http_async_client,
                )

                assert embeddings.http_client is http_client
                assert embeddings.http_async_client is http_async_client
                assert embeddings.model == "text-embedding-3-small"
                assert embeddings.request_timeout == 12.5
                assert embeddings.max_retries == 0

        assert http_client.is_closed
        assert http_async_client.is_closed

    asyncio.run(scenario())


def test_generates_embeddings_in_chunk_order() -> None:
    chunks = [
        TextChunk(chunk_index=0, page_number=1, text="First passage"),
        TextChunk(chunk_index=1, page_number=2, text="Second passage"),
    ]
    vectors = [[0.1] * 1536, [0.2] * 1536]
    embeddings = AsyncMock()
    embeddings.aembed_documents.return_value = vectors

    result = asyncio.run(generate_chunk_embeddings(chunks, embeddings))

    assert result == vectors
    embeddings.aembed_documents.assert_awaited_once_with(["First passage", "Second passage"])


def test_rejects_empty_chunks_before_calling_provider() -> None:
    embeddings = AsyncMock()

    with pytest.raises(ValueError, match="At least one chunk is required"):
        asyncio.run(generate_chunk_embeddings([], embeddings))

    embeddings.aembed_documents.assert_not_awaited()


@pytest.mark.parametrize(
    ("vectors", "message"),
    [
        ([], "Embedding count must match chunk count"),
        ([[0.1] * 1536, [0.2] * 1536], "Embedding count must match chunk count"),
        ([[0.1] * 1535], "Each embedding must have 1536 dimensions"),
        ([[0.1] * 1537], "Each embedding must have 1536 dimensions"),
        ([[float("nan")] + [0.1] * 1535], "Embedding values must be finite"),
        ([[float("inf")] + [0.1] * 1535], "Embedding values must be finite"),
        ([[float("-inf")] + [0.1] * 1535], "Embedding values must be finite"),
    ],
)
def test_rejects_invalid_embedding_response(vectors: list[list[float]], message: str) -> None:
    embeddings = AsyncMock()
    embeddings.aembed_documents.return_value = vectors
    chunks = [TextChunk(chunk_index=0, page_number=1, text="Passage")]

    with pytest.raises(ValueError, match=message):
        asyncio.run(generate_chunk_embeddings(chunks, embeddings))


def test_propagates_provider_failure() -> None:
    embeddings = AsyncMock()
    embeddings.aembed_documents.side_effect = TimeoutError("Provider timed out")
    chunks = [TextChunk(chunk_index=0, page_number=1, text="Passage")]

    with pytest.raises(TimeoutError, match="Provider timed out"):
        asyncio.run(generate_chunk_embeddings(chunks, embeddings))
