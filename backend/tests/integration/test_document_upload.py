from contextlib import closing
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.models.document import Document, DocumentStatus

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration


def test_upload_persists_document_and_file(
    integration_client: TestClient,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    filename = f"integration-{uuid4()}.pdf"
    bucket = integration_settings.s3_bucket

    try:
        response = integration_client.post(
            "/documents",
            files={"file": (filename, pdf_content, "application/pdf")},
        )

        assert response.status_code == 201, response.text
        response_data = response.json()
        document_id = UUID(response_data["id"])

        assert response_data["original_filename"] == filename
        assert response_data["content_type"] == "application/pdf"
        assert response_data["size_bytes"] == len(pdf_content)
        assert response_data["status"] == "uploaded"
        assert response_data["created_at"]

        with Session(integration_database_engine) as session:
            document = session.get(Document, document_id)

            assert document is not None
            assert document.original_filename == filename
            assert document.content_type == "application/pdf"
            assert document.size_bytes == len(pdf_content)
            assert document.status == DocumentStatus.UPLOADED
            assert document.created_at is not None

            storage_key = document.storage_key

        stored_file = integration_s3_client.get_object(
            Bucket=bucket,
            Key=storage_key,
        )

        with closing(stored_file["Body"]) as body:
            assert body.read() == pdf_content

        assert stored_file["ContentType"] == "application/pdf"

    finally:
        with Session(integration_database_engine) as session:
            documents = session.scalars(
                select(Document).where(Document.original_filename == filename)
            ).all()

            for document in documents:
                integration_s3_client.delete_object(
                    Bucket=bucket,
                    Key=document.storage_key,
                )
                session.delete(document)

            session.commit()
