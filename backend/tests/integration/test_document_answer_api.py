import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from documind.api.dependencies import get_answer_model, get_embeddings
from documind.documents.answer_generation import GeneratedAnswer
from documind.documents.answers import INSUFFICIENT_CONTEXT_ANSWER
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk

pytestmark = pytest.mark.integration


@pytest.fixture
def embeddings() -> MagicMock:
    provider = MagicMock(spec=Embeddings)
    provider.aembed_query.return_value = [1.0] + [0.0] * 1535
    return provider


@pytest.fixture
def answer_model() -> MagicMock:
    model = MagicMock(spec=ChatOpenAI)
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=GeneratedAnswer(
            answer="Passage 1 [chunk 1].",
            has_supporting_context=True,
            cited_chunk_indexes=[1],
        )
    )
    return model


@pytest.fixture
def answer_client(
    authenticated_client: TestClient, embeddings: MagicMock, answer_model: MagicMock
) -> TestClient:
    application = cast(FastAPI, authenticated_client.app)
    application.dependency_overrides[get_embeddings] = lambda: embeddings
    application.dependency_overrides[get_answer_model] = lambda: answer_model
    application.state.settings.retrieval_top_k = 2
    return authenticated_client


@pytest.fixture
def document_id(answer_client: TestClient, integration_database_engine: Engine) -> UUID:
    owner_id = UUID(answer_client.get("/auth/me").json()["id"])
    with Session(integration_database_engine) as session:
        document = Document(
            owner_id=owner_id,
            original_filename="search.pdf",
            storage_key=f"documents/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=100,
            status=DocumentStatus.READY,
        )
        session.add(document)
        session.flush()
        for index, coordinates in enumerate([(0.0, 1.0), (1.0, 0.0), (-1.0, 0.0)]):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    page_number=index + 1,
                    text=f"Passage {index}",
                    embedding=list(coordinates) + [0.0] * 1534,
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
                text="This other document must not appear.",
                embedding=[1.0] + [0.0] * 1535,
            )
        )
        session.commit()
        return document.id


def test_answer_uses_retrieved_passages_and_returns_stored_sources(
    answer_client: TestClient, document_id: UUID, embeddings: MagicMock, answer_model: MagicMock
) -> None:
    response = answer_client.post(
        f"/documents/{document_id}/answer", json={"question": "  Question  "}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "answer": "Passage 1 [chunk 1].",
        "sources": [
            {
                "document_id": str(document_id),
                "chunk_index": 1,
                "page_number": 2,
                "text": "Passage 1",
            }
        ],
    }
    embeddings.aembed_query.assert_awaited_once_with("Question")
    invocation = answer_model.with_structured_output.return_value.ainvoke
    invocation.assert_awaited_once()
    context = json.loads(invocation.call_args.args[0][1].content)
    assert context == {
        "question": "Question",
        "passages": [
            {"chunk_index": 1, "page_number": 2, "text": "Passage 1"},
            {"chunk_index": 0, "page_number": 1, "text": "Passage 0"},
        ],
    }


def test_foreign_and_missing_documents_do_not_call_models(
    other_authenticated_client: TestClient,
    document_id: UUID,
    embeddings: MagicMock,
    answer_model: MagicMock,
) -> None:
    application = cast(FastAPI, other_authenticated_client.app)
    application.dependency_overrides[get_embeddings] = lambda: embeddings
    application.dependency_overrides[get_answer_model] = lambda: answer_model
    for target_id in [document_id, uuid4()]:
        response = other_authenticated_client.post(
            f"/documents/{target_id}/answer", json={"question": "Question"}
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}
    embeddings.aembed_query.assert_not_awaited()
    answer_model.with_structured_output.assert_not_called()


@pytest.mark.parametrize(
    "document_status",
    [status for status in DocumentStatus if status != DocumentStatus.READY],
)
def test_unready_documents_do_not_call_models(
    answer_client: TestClient,
    document_id: UUID,
    embeddings: MagicMock,
    answer_model: MagicMock,
    integration_database_engine: Engine,
    document_status: DocumentStatus,
) -> None:
    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        document.status = document_status
        session.commit()
    response = answer_client.post(f"/documents/{document_id}/answer", json={"question": "Question"})
    assert response.status_code == 409
    assert response.json() == {"detail": "Document is not ready for questions"}
    embeddings.aembed_query.assert_not_awaited()
    answer_model.with_structured_output.assert_not_called()


def test_empty_retrieval_skips_generation(
    answer_client: TestClient,
    document_id: UUID,
    answer_model: MagicMock,
    integration_database_engine: Engine,
) -> None:
    with Session(integration_database_engine) as session:
        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        session.commit()
    response = answer_client.post(f"/documents/{document_id}/answer", json={"question": "Question"})
    assert response.status_code == 200
    assert response.json() == {"answer": INSUFFICIENT_CONTEXT_ANSWER, "sources": []}
    answer_model.with_structured_output.assert_not_called()


def test_insufficient_context_discards_generated_text(
    answer_client: TestClient, document_id: UUID, answer_model: MagicMock
) -> None:
    answer_model.with_structured_output.return_value.ainvoke.return_value = GeneratedAnswer(
        answer="Untrusted model text.", has_supporting_context=False, cited_chunk_indexes=[]
    )
    response = answer_client.post(f"/documents/{document_id}/answer", json={"question": "Question"})
    assert response.status_code == 200
    assert response.json() == {"answer": INSUFFICIENT_CONTEXT_ANSWER, "sources": []}


def test_citation_to_unretrieved_stored_chunk_is_rejected(
    answer_client: TestClient, document_id: UUID, answer_model: MagicMock
) -> None:
    answer_model.with_structured_output.return_value.ainvoke.return_value = GeneratedAnswer(
        answer="Not supplied to the model [chunk 2].",
        has_supporting_context=True,
        cited_chunk_indexes=[2],
    )
    response = answer_client.post(f"/documents/{document_id}/answer", json={"question": "Question"})
    assert response.status_code == 502
    assert response.json() == {"detail": "A valid answer could not be generated"}
