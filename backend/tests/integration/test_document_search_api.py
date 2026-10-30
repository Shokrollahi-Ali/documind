from typing import cast
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from documind.api.dependencies import get_embeddings
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk

pytestmark = pytest.mark.integration


@pytest.fixture
def embeddings() -> MagicMock:
    provider = MagicMock(spec=Embeddings)
    provider.aembed_query.return_value = [1.0] + [0.0] * 1535
    return provider


@pytest.fixture
def search_client(authenticated_client: TestClient, embeddings: MagicMock) -> TestClient:
    application = cast(FastAPI, authenticated_client.app)
    application.dependency_overrides[get_embeddings] = lambda: embeddings
    application.state.settings.retrieval_top_k = 2
    return authenticated_client


@pytest.fixture
def document_id(search_client: TestClient, integration_database_engine: Engine) -> UUID:
    owner_id = UUID(search_client.get("/auth/me").json()["id"])
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


def test_search_ranks_stored_chunks_and_returns_page_metadata(
    search_client: TestClient, document_id: UUID, embeddings: MagicMock
) -> None:
    response = search_client.post(
        f"/documents/{document_id}/search", json={"query": "  Question  "}
    )

    assert response.status_code == 200, response.text
    matches = response.json()["matches"]
    assert [match["chunk_index"] for match in matches] == [1, 0]
    assert [match["page_number"] for match in matches] == [2, 1]
    assert [match["text"] for match in matches] == ["Passage 1", "Passage 0"]
    assert [match["cosine_distance"] for match in matches] == pytest.approx([0, 1])
    assert all(match["document_id"] == str(document_id) for match in matches)
    embeddings.aembed_query.assert_awaited_once_with("Question")


def test_foreign_and_missing_documents_return_same_response_without_embedding(
    other_authenticated_client: TestClient,
    document_id: UUID,
    embeddings: MagicMock,
) -> None:
    application = cast(FastAPI, other_authenticated_client.app)
    application.dependency_overrides[get_embeddings] = lambda: embeddings

    for target_id in [document_id, uuid4()]:
        response = other_authenticated_client.post(
            f"/documents/{target_id}/search", json={"query": "Question"}
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}

    embeddings.aembed_query.assert_not_awaited()


@pytest.mark.parametrize(
    "document_status",
    [status for status in DocumentStatus if status != DocumentStatus.READY],
)
def test_unready_document_is_rejected_before_embedding(
    search_client: TestClient,
    document_id: UUID,
    embeddings: MagicMock,
    integration_database_engine: Engine,
    document_status: DocumentStatus,
) -> None:
    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        document.status = document_status
        session.commit()

    response = search_client.post(f"/documents/{document_id}/search", json={"query": "Question"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Document is not ready for search"}
    embeddings.aembed_query.assert_not_awaited()
