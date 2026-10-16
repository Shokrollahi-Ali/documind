from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.core.config import Settings
from documind.db.session import get_database_session
from documind.main import create_app
from documind.models.document import Document, DocumentStatus


@pytest.fixture
def client(s3_client_factory: MagicMock) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        s3_bucket="test-documents",
        max_upload_size_bytes=1024 * 1024,
    )
    application = create_app(settings)
    database_session = MagicMock(spec=AsyncSession)
    application.dependency_overrides[get_database_session] = lambda: database_session

    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def pdf_content() -> bytes:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        return file.getvalue()


def test_upload_returns_created_document(
    client: TestClient,
    pdf_content: bytes,
) -> None:
    document_id = uuid4()
    document = Document(
        id=document_id,
        original_filename="document.pdf",
        storage_key=f"documents/{document_id}.pdf",
        content_type="application/pdf",
        size_bytes=len(pdf_content),
        status=DocumentStatus.UPLOADED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with patch(
        "documind.api.documents.create_document",
        return_value=document,
    ) as create_document:
        response = client.post(
            "/documents",
            files={"file": ("document.pdf", pdf_content, "application/pdf")},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(document_id),
        "original_filename": "document.pdf",
        "content_type": "application/pdf",
        "size_bytes": len(pdf_content),
        "status": "uploaded",
        "created_at": "2026-01-01T00:00:00Z",
    }

    create_document.assert_awaited_once()
    arguments = create_document.call_args.kwargs
    assert arguments["bucket"] == "test-documents"
    assert arguments["metadata"].original_filename == "document.pdf"
    assert arguments["metadata"].size_bytes == len(pdf_content)
    assert arguments["file"].closed


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_status", "expected_detail"),
    [
        (
            "document.txt",
            "text/plain",
            415,
            "Only PDF files are supported",
        ),
        (
            "document.pdf",
            "application/pdf",
            422,
            "The uploaded file could not be read as a valid PDF",
        ),
    ],
)
def test_rejects_invalid_upload_without_calling_service(
    client: TestClient,
    filename: str,
    content_type: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    with patch("documind.api.documents.create_document") as create_document:
        response = client.post(
            "/documents",
            files={"file": (filename, b"Not a PDF", content_type)},
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    create_document.assert_not_called()


@pytest.mark.parametrize(
    ("service_error", "expected_detail"),
    [
        (
            EndpointConnectionError(endpoint_url="https://s3.example.com"),
            "Document storage is temporarily unavailable",
        ),
        (
            SQLAlchemyError("Internal database failure"),
            "Document persistence is temporarily unavailable",
        ),
    ],
)
def test_returns_service_unavailable_when_document_creation_fails(
    client: TestClient,
    pdf_content: bytes,
    service_error: Exception,
    expected_detail: str,
) -> None:
    with patch(
        "documind.api.documents.create_document",
        side_effect=service_error,
    ) as create_document:
        response = client.post(
            "/documents",
            files={"file": ("document.pdf", pdf_content, "application/pdf")},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": expected_detail}
    create_document.assert_awaited_once()
    assert create_document.call_args.kwargs["file"].closed


def test_get_returns_document(client: TestClient) -> None:
    document_id = uuid4()
    document = Document(
        id=document_id,
        original_filename="document.pdf",
        storage_key=f"documents/{document_id}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with patch(
        "documind.api.documents.get_document",
        return_value=document,
    ) as get_document:
        response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(document_id),
        "original_filename": "document.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1024,
        "status": "uploaded",
        "created_at": "2026-01-01T00:00:00Z",
    }

    get_document.assert_awaited_once()
    assert get_document.call_args.kwargs["document_id"] == document_id


def test_get_returns_not_found_when_document_is_missing(
    client: TestClient,
) -> None:
    document_id = uuid4()

    with patch(
        "documind.api.documents.get_document",
        return_value=None,
    ) as get_document:
        response = client.get(f"/documents/{document_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
    get_document.assert_awaited_once()
    assert get_document.call_args.kwargs["document_id"] == document_id


def test_get_rejects_invalid_document_id(client: TestClient) -> None:
    with patch("documind.api.documents.get_document") as get_document:
        response = client.get("/documents/not-a-uuid")

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors[0]["loc"] == ["path", "document_id"]
    get_document.assert_not_called()


def test_get_returns_service_unavailable_when_database_fails(
    client: TestClient,
) -> None:
    document_id = uuid4()

    with patch(
        "documind.api.documents.get_document",
        side_effect=SQLAlchemyError("Internal database failure"),
    ) as get_document:
        response = client.get(f"/documents/{document_id}")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Document persistence is temporarily unavailable",
    }
    get_document.assert_awaited_once()
    assert get_document.call_args.kwargs["document_id"] == document_id


def test_list_returns_paginated_documents(client: TestClient) -> None:
    documents = [
        Document(
            id=uuid4(),
            original_filename=f"document-{index}.pdf",
            storage_key=f"documents/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            status=DocumentStatus.UPLOADED,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for index in range(3)
    ]
    with patch("documind.api.documents.list_documents", return_value=documents) as service:
        response = client.get("/documents", params={"limit": 2, "offset": 4})

    assert response.status_code == 200
    data = response.json()
    assert data["has_more"] is True
    assert data["limit"] == 2
    assert data["offset"] == 4
    assert [item["id"] for item in data["items"]] == [str(item.id) for item in documents[:2]]
    assert "storage_key" not in data["items"][0]
    service.assert_awaited_once()
    assert service.call_args.kwargs["limit"] == 3
    assert service.call_args.kwargs["offset"] == 4


def test_list_returns_empty_page(client: TestClient) -> None:
    with patch("documind.api.documents.list_documents", return_value=[]):
        response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == {"items": [], "has_more": False, "limit": 10, "offset": 0}


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=abc", "offset=-1", "offset=1.5"])
def test_list_rejects_invalid_pagination(client: TestClient, query: str) -> None:
    with patch("documind.api.documents.list_documents") as service:
        response = client.get(f"/documents?{query}")

    assert response.status_code == 422
    service.assert_not_called()


def test_list_returns_service_unavailable_on_database_failure(client: TestClient) -> None:
    with patch("documind.api.documents.list_documents", side_effect=SQLAlchemyError("private")):
        response = client.get("/documents")

    assert response.status_code == 503
    assert response.json() == {"detail": "Document persistence is temporarily unavailable"}


def test_delete_returns_no_content(client: TestClient) -> None:
    document_id = uuid4()

    with patch(
        "documind.api.documents.delete_document",
        return_value=True,
    ) as delete_document:
        response = client.delete(f"/documents/{document_id}")

    assert response.status_code == 204
    assert response.content == b""

    delete_document.assert_awaited_once()
    arguments = delete_document.call_args.kwargs
    assert arguments["document_id"] == document_id
    assert arguments["bucket"] == "test-documents"


def test_delete_returns_not_found_when_document_is_missing(
    client: TestClient,
) -> None:
    document_id = uuid4()

    with patch(
        "documind.api.documents.delete_document",
        return_value=False,
    ) as delete_document:
        response = client.delete(f"/documents/{document_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}

    delete_document.assert_awaited_once()
    assert delete_document.call_args.kwargs["document_id"] == document_id


def test_delete_rejects_invalid_document_id(client: TestClient) -> None:
    with patch("documind.api.documents.delete_document") as delete_document:
        response = client.delete("/documents/not-a-uuid")

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors[0]["loc"] == ["path", "document_id"]
    delete_document.assert_not_called()


@pytest.mark.parametrize(
    ("service_error", "expected_detail"),
    [
        (
            EndpointConnectionError(endpoint_url="https://s3.example.com"),
            "Document storage is temporarily unavailable",
        ),
        (
            SQLAlchemyError("Internal database failure"),
            "Document persistence is temporarily unavailable",
        ),
    ],
)
def test_delete_returns_service_unavailable(
    client: TestClient,
    service_error: Exception,
    expected_detail: str,
) -> None:
    document_id = uuid4()

    with patch(
        "documind.api.documents.delete_document",
        side_effect=service_error,
    ) as delete_document:
        response = client.delete(f"/documents/{document_id}")

    assert response.status_code == 503
    assert response.json() == {"detail": expected_detail}
    delete_document.assert_awaited_once()
    assert delete_document.call_args.kwargs["document_id"] == document_id
