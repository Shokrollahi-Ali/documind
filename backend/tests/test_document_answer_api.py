from collections.abc import Iterator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.api.dependencies import get_answer_model, get_current_user, get_embeddings
from documind.core.config import Settings
from documind.db.session import get_database_session, get_database_session_factory
from documind.documents.answer_generation import AnswerGenerationError, AnswerRefusedError
from documind.documents.answer_sources import InvalidAnswerCitationError
from documind.documents.search import DocumentNotFoundError, DocumentNotReadyError
from documind.main import create_app
from documind.models.user import User
from documind.schemas.document_answer import DocumentAnswerResponse, DocumentAnswerSource


@pytest.fixture
def session_factory() -> MagicMock:
    return MagicMock(spec=async_sessionmaker)


@pytest.fixture
def embeddings() -> MagicMock:
    return MagicMock(spec=Embeddings)


@pytest.fixture
def answer_model() -> MagicMock:
    return MagicMock(spec=ChatOpenAI)


@pytest.fixture
def client(
    s3_client_factory: MagicMock,
    current_user: User,
    session_factory: MagicMock,
    embeddings: MagicMock,
    answer_model: MagicMock,
) -> Iterator[TestClient]:
    application = create_app(
        Settings(environment="test", openai_api_key=None, answer_model=None, retrieval_top_k=3)
    )
    application.dependency_overrides[get_current_user] = lambda: current_user
    application.dependency_overrides[get_database_session_factory] = lambda: session_factory
    application.dependency_overrides[get_embeddings] = lambda: embeddings
    application.dependency_overrides[get_answer_model] = lambda: answer_model

    with TestClient(application) as test_client:
        yield test_client


def test_answer_returns_citations_and_passes_authenticated_scope(
    client: TestClient,
    current_user: User,
    session_factory: MagicMock,
    embeddings: MagicMock,
    answer_model: MagicMock,
) -> None:
    document_id = uuid4()
    expected = DocumentAnswerResponse(
        answer="Refunds are available [chunk 2].",
        sources=[
            DocumentAnswerSource(
                document_id=document_id,
                chunk_index=2,
                page_number=3,
                text="Refunds are available within 30 days.",
            )
        ],
    )
    with patch("documind.api.document_answer.answer_document", return_value=expected) as service:
        response = client.post(
            f"/documents/{document_id}/answer",
            json={"question": "  What is the refund policy?  "},
        )
    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    service.assert_awaited_once_with(
        session_factory=session_factory,
        document_id=document_id,
        owner_id=current_user.id,
        question="What is the refund policy?",
        embeddings=embeddings,
        model=answer_model,
        limit=3,
    )


def test_insufficient_context_is_a_successful_response(client: TestClient) -> None:
    expected = DocumentAnswerResponse(answer="Insufficient evidence.", sources=[])
    with patch("documind.api.document_answer.answer_document", return_value=expected):
        response = client.post(f"/documents/{uuid4()}/answer", json={"question": "Question"})
    assert response.status_code == 200
    assert response.json() == expected.model_dump()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 2001},
        {"question": None},
        {"question": 123},
        {"question": "Question", "owner_id": str(uuid4())},
        {"question": "Question", "limit": 1000},
    ],
)
def test_invalid_request_does_not_call_answer(client: TestClient, body: dict[str, object]) -> None:
    with patch("documind.api.document_answer.answer_document") as answer_service:
        response = client.post(f"/documents/{uuid4()}/answer", json=body)

    assert response.status_code == 422
    answer_service.assert_not_awaited()


def test_invalid_document_id_does_not_call_answer(client: TestClient) -> None:
    with patch("documind.api.document_answer.answer_document") as answer_service:
        response = client.post("/documents/not-a-uuid/answer", json={"question": "Question"})

    assert response.status_code == 422
    answer_service.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (DocumentNotFoundError("private"), 404, "Document not found"),
        (AnswerGenerationError("private"), 502, "A valid answer could not be generated"),
        (InvalidAnswerCitationError("private"), 502, "A valid answer could not be generated"),
        (AnswerRefusedError("private"), 422, "The model declined to answer this question"),
        (DocumentNotReadyError("private"), 409, "Document is not ready for questions"),
        (SQLAlchemyError("private"), 503, "Document answer generation is temporarily unavailable"),
        (
            APITimeoutError(request=httpx2.Request("POST", "https://example.com")),
            503,
            "Document answer generation is temporarily unavailable",
        ),
        (
            APIConnectionError(request=httpx2.Request("POST", "https://example.com")),
            503,
            "Document answer generation is temporarily unavailable",
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
            "Document answer generation is temporarily unavailable",
        ),
    ],
)
def test_service_errors_return_safe_responses(
    client: TestClient, error: Exception, expected_status: int, expected_detail: str
) -> None:
    with patch("documind.api.document_answer.answer_document", side_effect=error) as answer_service:
        response = client.post(f"/documents/{uuid4()}/answer", json={"question": "Question"})

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    answer_service.assert_awaited_once()


@pytest.mark.parametrize("authentication", ["missing", "invalid", "database-error"])
def test_answer_requires_authentication(client: TestClient, authentication: str) -> None:
    application = cast(FastAPI, client.app)
    application.dependency_overrides.pop(get_current_user)
    database_session = MagicMock(spec=AsyncSession)
    database_session.begin.return_value = AsyncMock()
    application.dependency_overrides[get_database_session] = lambda: database_session
    if authentication != "missing":
        client.cookies.set(application.state.settings.session_cookie_name, "invalid-token")

    with (
        patch("documind.api.dependencies.get_session_user", return_value=None) as lookup,
        patch("documind.api.document_answer.answer_document") as answer_service,
    ):
        if authentication == "database-error":
            lookup.side_effect = SQLAlchemyError("private")
        response = client.post(f"/documents/{uuid4()}/answer", json={"question": "Question"})

    if authentication == "database-error":
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication is temporarily unavailable"}
    else:
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}
    answer_service.assert_not_awaited()
    if authentication == "missing":
        lookup.assert_not_awaited()


def test_missing_embedding_configuration_disables_answer(client: TestClient) -> None:
    application = cast(FastAPI, client.app)
    application.dependency_overrides.pop(get_embeddings)
    with patch("documind.api.document_answer.answer_document") as answer_service:
        response = client.post(f"/documents/{uuid4()}/answer", json={"question": "Question"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Document search is unavailable"}
    answer_service.assert_not_awaited()


def test_missing_answer_configuration_disables_answers(client: TestClient) -> None:
    application = cast(FastAPI, client.app)
    application.dependency_overrides.pop(get_answer_model)
    with patch("documind.api.document_answer.answer_document") as service:
        response = client.post(f"/documents/{uuid4()}/answer", json={"question": "Question"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Document answer generation is unavailable"}
    service.assert_not_awaited()


def test_accepts_maximum_question_length(client: TestClient) -> None:
    with patch(
        "documind.api.document_answer.answer_document",
        return_value=DocumentAnswerResponse(answer="Insufficient evidence.", sources=[]),
    ) as service:
        response = client.post(f"/documents/{uuid4()}/answer", json={"question": "x" * 2000})
    assert response.status_code == 200
    assert service.call_args.kwargs["question"] == "x" * 2000
