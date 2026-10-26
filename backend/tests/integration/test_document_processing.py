import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.extraction import ExtractedPage, NoExtractableTextError
from documind.documents.processing import (
    extract_and_store_document_pages,
    extract_stored_document,
)
from documind.models.document import Document, DocumentStatus
from documind.models.document_page import DocumentPage

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration


def test_uploaded_pdf_pages_are_extracted_and_saved(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_factory: Callable[[list[bytes]], bytes],
) -> None:
    pdf = pdf_factory(
        [
            b"BT /F1 12 Tf 72 720 Td (First page) Tj ET",
            b"",
            b"BT /F1 12 Tf 72 720 Td (Third page) Tj ET",
        ]
    )
    current_user = authenticated_client.get("/auth/me")
    assert current_user.status_code == 200, current_user.text
    owner_id = UUID(current_user.json()["id"])

    upload = authenticated_client.post(
        "/documents",
        files={"file": ("processing-test.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])

    async def process_document() -> bool:
        engine = create_database_engine(integration_settings)
        session_factory = create_session_factory(engine)

        try:
            return await extract_and_store_document_pages(
                session_factory=session_factory,
                s3_client=integration_s3_client,
                bucket=integration_settings.s3_bucket,
                document_id=document_id,
                owner_id=owner_id,
                lease_seconds=integration_settings.processing_lease_seconds,
            )
        finally:
            await engine.dispose()

    assert asyncio.run(process_document()) is True

    with Session(integration_database_engine) as session:
        pages = session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        ).all()

        assert [(page.page_number, page.text) for page in pages] == [
            (1, "First page"),
            (3, "Third page"),
        ]
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.EXTRACTED
        assert document.processing_attempt_id is None
        assert document.processing_lease_expires_at is None


def test_blank_uploaded_pdf_records_processing_failure(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    current_user = authenticated_client.get("/auth/me")
    assert current_user.status_code == 200, current_user.text
    owner_id = UUID(current_user.json()["id"])

    upload = authenticated_client.post(
        "/documents",
        files={"file": ("blank-processing.pdf", pdf_content, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])

    async def process_document() -> None:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)
            await extract_and_store_document_pages(
                session_factory=session_factory,
                s3_client=integration_s3_client,
                bucket=integration_settings.s3_bucket,
                document_id=document_id,
                owner_id=owner_id,
                lease_seconds=integration_settings.processing_lease_seconds,
            )
        finally:
            await engine.dispose()

    with pytest.raises(NoExtractableTextError):
        asyncio.run(process_document())

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.FAILED
        assert document.processing_attempt_id is None
        assert document.processing_lease_expires_at is None
        pages = session.scalars(
            select(DocumentPage).where(DocumentPage.document_id == document_id)
        ).all()
        assert pages == []


def test_extracts_text_and_page_numbers_from_stored_pdf(
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_factory: Callable[[list[bytes]], bytes],
) -> None:
    bucket = integration_settings.s3_bucket
    storage_key = f"documents/{uuid4()}.pdf"
    pdf = pdf_factory(
        [
            b"BT /F1 12 Tf 72 720 Td (First page) Tj ET",
            b"",
            b"BT /F1 12 Tf 72 720 Td (Third page) Tj ET",
        ]
    )

    try:
        integration_s3_client.put_object(
            Bucket=bucket,
            Key=storage_key,
            Body=pdf,
            ContentType="application/pdf",
        )

        pages = asyncio.run(
            extract_stored_document(
                s3_client=integration_s3_client,
                bucket=bucket,
                storage_key=storage_key,
            )
        )

        assert pages == [
            ExtractedPage(page_number=1, text="First page"),
            ExtractedPage(page_number=3, text="Third page"),
        ]
    finally:
        integration_s3_client.delete_object(
            Bucket=bucket,
            Key=storage_key,
        )


def test_stored_blank_pdf_has_no_extractable_text(
    integration_s3_client: "S3Client",
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    bucket = integration_settings.s3_bucket
    storage_key = f"documents/{uuid4()}.pdf"

    try:
        integration_s3_client.put_object(
            Bucket=bucket,
            Key=storage_key,
            Body=pdf_content,
            ContentType="application/pdf",
        )

        with pytest.raises(NoExtractableTextError):
            asyncio.run(
                extract_stored_document(
                    s3_client=integration_s3_client,
                    bucket=bucket,
                    storage_key=storage_key,
                )
            )
    finally:
        integration_s3_client.delete_object(
            Bucket=bucket,
            Key=storage_key,
        )
