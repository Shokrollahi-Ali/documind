import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from documind.api.dependencies import get_embeddings
from documind.core.config import Settings
from documind.db.session import get_database_session_factory
from documind.documents.retrieval import RetrievedChunk
from documind.main import create_app
from documind.schemas.document_search import DocumentSearchMatch, DocumentSearchRequest


@pytest.mark.parametrize("startup_fails", [False, True])
def test_embedding_lifecycle_closes_resources(
    s3_client_factory: MagicMock, startup_fails: bool
) -> None:
    settings = Settings(openai_api_key=SecretStr("test-key"))
    application = create_app(settings)
    engine = AsyncMock(spec=AsyncEngine)
    embeddings = MagicMock(spec=Embeddings)

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            assert application.state.embeddings is embeddings
            request = Request({"type": "http", "app": application})
            assert await get_embeddings(request) is embeddings
            factory = await get_database_session_factory(request)
            assert factory is application.state.session_factory
            assert not embedding_factory.call_args.kwargs["http_client"].is_closed
            assert not embedding_factory.call_args.kwargs["http_async_client"].is_closed
            engine.dispose.assert_not_awaited()

    with (
        patch("documind.main.create_database_engine", return_value=engine),
        patch("documind.main.create_embeddings", return_value=embeddings) as embedding_factory,
    ):
        if startup_fails:
            embedding_factory.side_effect = ValueError("Invalid embedding configuration")
            with pytest.raises(ValueError, match="Invalid embedding configuration"):
                asyncio.run(run_lifespan())
        else:
            asyncio.run(run_lifespan())

        embedding_factory.assert_called_once()
        assert embedding_factory.call_args.args == (settings,)
        assert embedding_factory.call_args.kwargs["http_client"].is_closed
        assert embedding_factory.call_args.kwargs["http_async_client"].is_closed
        engine.dispose.assert_awaited_once_with()
        s3_client_factory.return_value.close.assert_called_once_with()


def test_missing_key_allows_startup_but_disables_search(s3_client_factory: MagicMock) -> None:
    application = create_app(Settings(openai_api_key=None))
    engine = AsyncMock(spec=AsyncEngine)

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            request = Request({"type": "http", "app": application})
            with pytest.raises(HTTPException) as error:
                await get_embeddings(request)
            assert error.value.status_code == 503
            assert error.value.detail == "Document search is unavailable"

    with (
        patch("documind.main.create_database_engine", return_value=engine),
        patch("documind.main.create_embeddings") as embedding_factory,
    ):
        asyncio.run(run_lifespan())
        embedding_factory.assert_not_called()
    engine.dispose.assert_awaited_once_with()
    s3_client_factory.return_value.close.assert_called_once_with()


@pytest.mark.parametrize("query", ["", "   ", "x" * 2001])
def test_rejects_invalid_search_query(query: str) -> None:
    with pytest.raises(ValidationError):
        DocumentSearchRequest(query=query)


def test_normalizes_query_and_rejects_unknown_fields() -> None:
    assert DocumentSearchRequest(query="  Question  ").query == "Question"
    assert len(DocumentSearchRequest(query="x" * 2000).query) == 2000
    with pytest.raises(ValidationError):
        DocumentSearchRequest.model_validate({"query": "Question", "owner_id": "unexpected"})


def test_converts_retrieved_chunk_to_response() -> None:
    chunk = RetrievedChunk(uuid4(), 2, 3, "Source passage", 0.25)
    match = DocumentSearchMatch.model_validate(chunk)
    assert match.model_dump() == {
        "document_id": chunk.document_id,
        "chunk_index": 2,
        "page_number": 3,
        "text": "Source passage",
        "cosine_distance": 0.25,
    }


@pytest.mark.parametrize("limit", [0, -1, 21])
def test_rejects_invalid_retrieval_limit(limit: int) -> None:
    with pytest.raises(ValidationError, match="retrieval_top_k"):
        Settings(retrieval_top_k=limit)


@pytest.mark.parametrize("limit", [1, 5, 20])
def test_reads_retrieval_limit_from_environment(
    monkeypatch: pytest.MonkeyPatch, limit: int
) -> None:
    monkeypatch.setenv("DOCUMIND_RETRIEVAL_TOP_K", str(limit))
    assert Settings(_env_file=None).retrieval_top_k == limit
