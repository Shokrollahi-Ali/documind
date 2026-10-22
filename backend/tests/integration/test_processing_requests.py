from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.models.document import Document
from documind.models.document_processing_request import DocumentProcessingRequest

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration


def test_rejects_duplicate_processing_request(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("duplicate-request.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        original_request = session.scalars(
            select(DocumentProcessingRequest).where(
                DocumentProcessingRequest.document_id == document_id
            )
        ).one()
        original_request_id = original_request.id

        with pytest.raises(IntegrityError, match="uq_document_processing_requests_document_id"):
            with session.begin_nested():
                session.add(DocumentProcessingRequest(document_id=document_id))
                session.flush()

        remaining_request = session.scalars(
            select(DocumentProcessingRequest).where(
                DocumentProcessingRequest.document_id == document_id
            )
        ).one()
        assert remaining_request.id == original_request_id


def test_rejects_processing_request_without_document(
    integration_database_engine: Engine,
) -> None:
    with Session(integration_database_engine) as session:
        with pytest.raises(
            IntegrityError,
            match="fk_document_processing_requests_document_id_documents",
        ):
            with session.begin_nested():
                session.add(DocumentProcessingRequest(document_id=uuid4()))
                session.flush()


def test_request_insert_failure_rolls_back_document_and_removes_uploaded_file(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    expected_document_id = uuid4()
    missing_document_id = uuid4()
    storage_key = f"documents/{expected_document_id}.pdf"
    bucket = integration_settings.s3_bucket

    def create_invalid_request(document_id: UUID) -> DocumentProcessingRequest:
        assert document_id == expected_document_id
        stored_file = integration_s3_client.head_object(Bucket=bucket, Key=storage_key)
        assert stored_file["ContentLength"] == len(pdf_content)
        return DocumentProcessingRequest(document_id=missing_document_id)

    try:
        with (
            patch("documind.documents.service.uuid4", return_value=expected_document_id),
            patch(
                "documind.documents.service.DocumentProcessingRequest",
                side_effect=create_invalid_request,
            ),
        ):
            response = authenticated_client.post(
                "/documents",
                files={"file": ("failed-request.pdf", pdf_content, "application/pdf")},
            )

        assert response.status_code == 503, response.text

        with Session(integration_database_engine) as session:
            assert session.get(Document, expected_document_id) is None
            requests = session.scalars(
                select(DocumentProcessingRequest).where(
                    DocumentProcessingRequest.document_id.in_(
                        [expected_document_id, missing_document_id]
                    )
                )
            ).all()
            assert requests == []

        with pytest.raises(ClientError) as exception_info:
            integration_s3_client.head_object(Bucket=bucket, Key=storage_key)

        assert exception_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    finally:
        integration_s3_client.delete_object(Bucket=bucket, Key=storage_key)
