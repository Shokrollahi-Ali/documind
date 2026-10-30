from collections.abc import Sequence
from math import isfinite

import httpx
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from documind.core.config import Settings
from documind.documents.chunking import TextChunk


def create_embeddings(
    settings: Settings,
    *,
    http_client: httpx.Client,
    http_async_client: httpx.AsyncClient,
) -> OpenAIEmbeddings:
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value().strip():
        raise ValueError("DOCUMIND_OPENAI_API_KEY must be set to generate embeddings")

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
        request_timeout=settings.embedding_request_timeout_seconds,
        max_retries=0,
        http_client=http_client,
        http_async_client=http_async_client,
    )


def validate_embedding(vector: Sequence[float]) -> None:
    if len(vector) != 1536:
        raise ValueError("Each embedding must have 1536 dimensions")

    if not all(isfinite(value) for value in vector):
        raise ValueError("Embedding values must be finite")


async def generate_chunk_embeddings(
    chunks: Sequence[TextChunk],
    embeddings: Embeddings,
) -> list[list[float]]:
    if not chunks:
        raise ValueError("At least one chunk is required")

    vectors = await embeddings.aembed_documents([chunk.text for chunk in chunks])

    if len(vectors) != len(chunks):
        raise ValueError("Embedding count must match chunk count")

    for vector in vectors:
        validate_embedding(vector)

    return vectors


async def generate_query_embedding(
    query: str,
    embeddings: Embeddings,
) -> list[float]:
    query = query.strip()

    if not query:
        raise ValueError("Query must not be empty")

    vector = await embeddings.aembed_query(query)
    validate_embedding(vector)

    return vector
