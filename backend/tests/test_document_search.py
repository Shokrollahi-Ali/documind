import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from documind.documents.retrieval import RetrievedChunk
from documind.documents.search import (
    DocumentNotFoundError,
    DocumentNotReadyError,
    search_document,
)
from documind.models.document import Document, DocumentStatus


@pytest.mark.parametrize(
    "status", [None, *[s for s in DocumentStatus if s != DocumentStatus.READY]]
)
def test_unavailable_document_does_not_call_embeddings(status: DocumentStatus | None) -> None:
    factory = MagicMock(return_value=AsyncMock())
    embeddings = AsyncMock()
    document_id, owner_id = uuid4(), uuid4()
    error = DocumentNotFoundError if status is None else DocumentNotReadyError

    with (
        patch("documind.documents.search.get_document", new_callable=AsyncMock) as lookup,
        patch("documind.documents.search.retrieve_document_chunks") as retrieve,
    ):
        lookup.return_value = None if status is None else Document(status=status)
        with pytest.raises(error):
            asyncio.run(
                search_document(factory, document_id, owner_id, "Question", embeddings, limit=5)
            )

        lookup.assert_awaited_once_with(
            database_session=factory.return_value.__aenter__.return_value,
            document_id=document_id,
            owner_id=owner_id,
        )
        embeddings.aembed_query.assert_not_awaited()
        retrieve.assert_not_awaited()
        factory.return_value.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_limit_does_not_open_session(limit: int) -> None:
    factory = MagicMock()
    embeddings = AsyncMock()
    with pytest.raises(ValueError, match="Search limit must be positive"):
        asyncio.run(search_document(factory, uuid4(), uuid4(), "Question", embeddings, limit=limit))
    factory.assert_not_called()
    embeddings.aembed_query.assert_not_awaited()


@pytest.mark.parametrize("empty_result", [False, True])
def test_releases_session_before_embedding_and_passes_search_scope(empty_result: bool) -> None:
    read_session, retrieval_session = AsyncMock(), AsyncMock()
    factory = MagicMock(side_effect=[read_session, retrieval_session])
    embeddings = AsyncMock()
    document_id, owner_id = uuid4(), uuid4()
    vector = [0.1] * 1536
    matches = [] if empty_result else [RetrievedChunk(document_id, 0, 1, "Passage", 0.2)]

    async def embed(query: str) -> list[float]:
        assert query == "Question"
        read_session.__aexit__.assert_awaited_once()
        assert factory.call_count == 1
        return vector

    embeddings.aembed_query.side_effect = embed
    with (
        patch(
            "documind.documents.search.get_document",
            return_value=Document(status=DocumentStatus.READY),
        ),
        patch(
            "documind.documents.search.retrieve_document_chunks", return_value=matches
        ) as retrieve,
    ):
        result = asyncio.run(
            search_document(factory, document_id, owner_id, " Question ", embeddings, limit=3)
        )
        assert result == matches
        retrieve.assert_awaited_once_with(
            database_session=retrieval_session.__aenter__.return_value,
            document_id=document_id,
            owner_id=owner_id,
            query_embedding=vector,
            limit=3,
        )
        retrieval_session.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("failure", ["timeout", "invalid_vector", "blank_query"])
def test_embedding_failure_stops_retrieval(failure: str) -> None:
    factory = MagicMock(return_value=AsyncMock())
    embeddings = AsyncMock()
    query = "Question"
    error: type[Exception] = ValueError
    if failure == "timeout":
        embeddings.aembed_query.side_effect = TimeoutError("Provider timed out")
        error = TimeoutError
    elif failure == "blank_query":
        query = "   "
    else:
        embeddings.aembed_query.return_value = [0.1]

    with (
        patch(
            "documind.documents.search.get_document",
            return_value=Document(status=DocumentStatus.READY),
        ),
        patch("documind.documents.search.retrieve_document_chunks") as retrieve,
    ):
        with pytest.raises(error):
            asyncio.run(search_document(factory, uuid4(), uuid4(), query, embeddings, limit=5))
        retrieve.assert_not_awaited()
        assert factory.call_count == 1
        factory.return_value.__aexit__.assert_awaited_once()
        if failure == "blank_query":
            embeddings.aembed_query.assert_not_awaited()
