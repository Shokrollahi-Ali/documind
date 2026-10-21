import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from documind.core.config import Settings
from documind.documents.extraction import ExtractedPage, NoExtractableTextError
from documind.documents.processing import extract_stored_document

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration


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
