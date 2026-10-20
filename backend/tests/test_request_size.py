from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from documind.api.dependencies import get_current_user
from documind.api.request_size import MULTIPART_OVERHEAD_BYTES
from documind.core.config import Settings
from documind.db.session import get_database_session
from documind.main import create_app
from documind.models.user import User

MAX_UPLOAD_SIZE_BYTES = 1024
MAX_BODY_SIZE_BYTES = MAX_UPLOAD_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES
TOO_LARGE_DETAIL = f"Request body must not exceed {MAX_BODY_SIZE_BYTES} bytes"


@pytest.fixture
def client(s3_client_factory: MagicMock, current_user: User) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        s3_bucket="test-documents",
        max_upload_size_bytes=MAX_UPLOAD_SIZE_BYTES,
    )
    application = create_app(settings)
    database_session = MagicMock(spec=AsyncSession)
    application.dependency_overrides[get_database_session] = lambda: database_session
    application.dependency_overrides[get_current_user] = lambda: current_user

    with TestClient(application) as test_client:
        yield test_client


def test_rejects_oversized_content_length_before_reaching_the_route(client: TestClient) -> None:
    with patch("documind.api.documents.create_document") as create_document:
        response = client.post(
            "/documents",
            files={"file": ("large.pdf", b"x" * (MAX_BODY_SIZE_BYTES + 1), "application/pdf")},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}
    create_document.assert_not_called()


def test_rejects_oversized_chunked_body_without_content_length(client: TestClient) -> None:
    boundary = "documind-test-boundary"
    chunk = b"x" * 4096
    chunk_count = MAX_BODY_SIZE_BYTES // len(chunk) + 2

    def body() -> Iterator[bytes]:
        yield (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="large.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        for _ in range(chunk_count):
            yield chunk
        yield f"\r\n--{boundary}--\r\n".encode()

    with patch("documind.api.documents.create_document") as create_document:
        response = client.post(
            "/documents",
            content=body(),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}
    create_document.assert_not_called()


def test_allows_a_file_at_the_upload_limit_with_a_maximum_length_filename(
    client: TestClient,
) -> None:
    filename = f"{'a' * 251}.pdf"

    response = client.post(
        "/documents",
        files={"file": (filename, b"x" * MAX_UPLOAD_SIZE_BYTES, "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "The uploaded file could not be read as a valid PDF"}
