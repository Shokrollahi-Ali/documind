from contextlib import closing
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.models.document import Document

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration


def test_other_user_cannot_access_document_or_change_its_owner(
    authenticated_client: TestClient,
    other_authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    owner_id = UUID(authenticated_client.get("/auth/me").json()["id"])
    other_user_id = UUID(other_authenticated_client.get("/auth/me").json()["id"])

    upload = authenticated_client.post(
        "/documents",
        data={"owner_id": str(other_user_id)},
        files={"file": ("private-document.pdf", pdf_content, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])

    with Session(integration_database_engine) as database_session:
        document = database_session.get(Document, document_id)
        assert document is not None
        assert document.owner_id == owner_id
        storage_key = document.storage_key

    listing = other_authenticated_client.get("/documents", params={"owner_id": str(owner_id)})
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "has_more": False, "limit": 10, "offset": 0}

    for target_id in [document_id, uuid4()]:
        retrieval = other_authenticated_client.get(
            f"/documents/{target_id}", params={"owner_id": str(owner_id)}
        )
        deletion = other_authenticated_client.delete(
            f"/documents/{target_id}", params={"owner_id": str(owner_id)}
        )
        assert retrieval.status_code == 404
        assert deletion.status_code == 404
        assert retrieval.json() == deletion.json() == {"detail": "Document not found"}

    with Session(integration_database_engine) as database_session:
        remaining_document = database_session.get(Document, document_id)
        assert remaining_document is not None
        assert remaining_document.owner_id == owner_id

    stored_file = integration_s3_client.get_object(
        Bucket=integration_settings.s3_bucket, Key=storage_key
    )
    with closing(stored_file["Body"]) as body:
        assert body.read() == pdf_content

    owner_response = authenticated_client.get(f"/documents/{document_id}")
    assert owner_response.status_code == 200
    assert owner_response.json() == upload.json()
