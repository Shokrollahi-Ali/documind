import asyncio
from contextlib import closing
from tempfile import TemporaryFile
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.models.document import Document, DocumentStatus
from documind.storage.s3 import download_document_file

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration


def test_uploaded_document_can_be_retrieved_and_deleted(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    filename = f"integration-{uuid4()}.pdf"
    bucket = integration_settings.s3_bucket
    storage_key: str | None = None
    current_user = authenticated_client.get("/auth/me")
    assert current_user.status_code == 200
    owner_id = UUID(current_user.json()["id"])

    try:
        response = authenticated_client.post(
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
            assert document.owner_id == owner_id
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

        with TemporaryFile(mode="w+b") as downloaded_file:
            asyncio.run(
                download_document_file(
                    s3_client=integration_s3_client,
                    file=downloaded_file,
                    bucket=bucket,
                    storage_key=storage_key,
                )
            )
            downloaded_file.seek(0)
            assert downloaded_file.read() == pdf_content

        retrieval_response = authenticated_client.get(f"/documents/{document_id}")

        assert retrieval_response.status_code == 200, retrieval_response.text
        assert retrieval_response.json() == response_data

        deletion_response = authenticated_client.delete(f"/documents/{document_id}")

        assert deletion_response.status_code == 204, deletion_response.text
        assert deletion_response.content == b""

        with Session(integration_database_engine) as session:
            assert session.get(Document, document_id) is None

        with pytest.raises(ClientError) as exception_info:
            integration_s3_client.head_object(
                Bucket=bucket,
                Key=storage_key,
            )

        assert exception_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404

        assert authenticated_client.get(f"/documents/{document_id}").status_code == 404
        assert authenticated_client.delete(f"/documents/{document_id}").status_code == 404
    finally:
        if storage_key is not None:
            integration_s3_client.delete_object(
                Bucket=bucket,
                Key=storage_key,
            )
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
