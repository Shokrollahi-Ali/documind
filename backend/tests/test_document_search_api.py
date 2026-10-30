from collections.abc import Iterator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from openai import APIConnectionError, APIStatusError, APITimeoutError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.api.dependencies import get_current_user, get_embeddings
from documind.core.config import Settings
from documind.db.session import get_database_session, get_database_session_factory
from documind.documents.retrieval import RetrievedChunk
from documind.documents.search import DocumentNotFoundError, DocumentNotReadyError
from documind.main import create_app
from documind.models.user import User


@pytest.fixture
def session_factory() -> MagicMock:
    return MagicMock(spec=async_sessionmaker)


@pytest.fixture
def embeddings() -> MagicMock:
    return MagicMock(spec=Embeddings)


@pytest.fixture
def client(
    s3_client_factory: MagicMock,
    current_user: User,
    session_factory: MagicMock,
    embeddings: MagicMock,
) -> Iterator[TestClient]:
    application = create_app(Settings(environment="test", openai_api_key=None, retrieval_top_k=3))
    application.dependency_overrides[get_current_user] = lambda: current_user
    application.dependency_overrides[get_database_session_factory] = lambda: session_factory
    application.dependency_overrides[get_embeddings] = lambda: embeddings

    with TestClient(application) as test_client:
        yield test_client


def test_search_returns_matching_passages(
    client: TestClient,
    current_user: User,
    session_factory: MagicMock,
    embeddings: MagicMock,
) -> None:
    document_id = uuid4()
    chunks = [
        RetrievedChunk(document_id, 2, 3, "Refunds are available within 30 days.", 0.15),
        RetrievedChunk(document_id, 4, 5, "Contact support to request a refund.", 0.3),
    ]
    with patch(
        "documind.api.document_search.search_document", return_value=chunks
    ) as search_service:
        response = client.post(
            f"/documents/{document_id}/search",
            json={"query": "  What is the refund policy?  "},
        )

    assert response.status_code == 200
    assert response.json() == {
        "matches": [
            {
                "document_id": str(chunk.document_id),
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "text": chunk.text,
                "cosine_distance": chunk.cosine_distance,
            }
            for chunk in chunks
        ]
    }
    search_service.assert_awaited_once_with(
        session_factory=session_factory,
        document_id=document_id,
        owner_id=current_user.id,
        query="What is the refund policy?",
        embeddings=embeddings,
        limit=3,
    )


def test_search_returns_empty_matches(client: TestClient) -> None:
    with patch("documind.api.document_search.search_document", return_value=[]):
        response = client.post(f"/documents/{uuid4()}/search", json={"query": "Question"})

    assert response.status_code == 200
    assert response.json() == {"matches": []}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 2001},
        {"query": None},
        {"query": 123},
        {"query": "Question", "owner_id": str(uuid4())},
        {"query": "Question", "limit": 1000},
    ],
)
def test_invalid_request_does_not_call_search(client: TestClient, body: dict[str, object]) -> None:
    with patch("documind.api.document_search.search_document") as search_service:
        response = client.post(f"/documents/{uuid4()}/search", json=body)

    assert response.status_code == 422
    search_service.assert_not_awaited()


def test_invalid_document_id_does_not_call_search(client: TestClient) -> None:
    with patch("documind.api.document_search.search_document") as search_service:
        response = client.post("/documents/not-a-uuid/search", json={"query": "Question"})

    assert response.status_code == 422
    search_service.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (DocumentNotFoundError("private"), 404, "Document not found"),
        (DocumentNotReadyError("private"), 409, "Document is not ready for search"),
        (SQLAlchemyError("private"), 503, "Document search is temporarily unavailable"),
        (
            APITimeoutError(request=httpx2.Request("POST", "https://example.com")),
            503,
            "Document search is temporarily unavailable",
        ),
        (
            APIConnectionError(request=httpx2.Request("POST", "https://example.com")),
            503,
            "Document search is temporarily unavailable",
        ),
        (
            APIStatusError(
                "private",
                response=httpx2.Response(
                    429, request=httpx2.Request("POST", "https://example.com")
                ),
                body={"private": "provider details"},
            ),
            503,
            "Document search is temporarily unavailable",
        ),
    ],
)
def test_service_errors_return_safe_responses(
    client: TestClient, error: Exception, expected_status: int, expected_detail: str
) -> None:
    with patch("documind.api.document_search.search_document", side_effect=error) as search_service:
        response = client.post(f"/documents/{uuid4()}/search", json={"query": "Question"})

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    search_service.assert_awaited_once()


@pytest.mark.parametrize("authentication", ["missing", "invalid", "database-error"])
def test_search_requires_authentication(client: TestClient, authentication: str) -> None:
    application = cast(FastAPI, client.app)
    application.dependency_overrides.pop(get_current_user)
    database_session = MagicMock(spec=AsyncSession)
    database_session.begin.return_value = AsyncMock()
    application.dependency_overrides[get_database_session] = lambda: database_session
    if authentication != "missing":
        client.cookies.set(application.state.settings.session_cookie_name, "invalid-token")

    with (
        patch("documind.api.dependencies.get_session_user", return_value=None) as lookup,
        patch("documind.api.document_search.search_document") as search_service,
    ):
        if authentication == "database-error":
            lookup.side_effect = SQLAlchemyError("private")
        response = client.post(f"/documents/{uuid4()}/search", json={"query": "Question"})

    if authentication == "database-error":
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication is temporarily unavailable"}
    else:
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}
    search_service.assert_not_awaited()
    if authentication == "missing":
        lookup.assert_not_awaited()


def test_missing_embedding_configuration_disables_search(client: TestClient) -> None:
    application = cast(FastAPI, client.app)
    application.dependency_overrides.pop(get_embeddings)
    with patch("documind.api.document_search.search_document") as search_service:
        response = client.post(f"/documents/{uuid4()}/search", json={"query": "Question"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Document search is unavailable"}
    search_service.assert_not_awaited()
