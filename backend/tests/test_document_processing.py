import asyncio
from typing import BinaryIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import EndpointConnectionError

from documind.documents.extraction import (
    ExtractedPage,
    NoExtractableTextError,
    PdfExtractionError,
)
from documind.documents.processing import extract_stored_document


def test_download_failure_closes_temporary_file() -> None:
    s3_client = MagicMock()
    error = EndpointConnectionError(endpoint_url="http://localhost:4566")

    with (
        patch(
            "documind.documents.processing.download_document_file",
            new_callable=AsyncMock,
            side_effect=error,
        ) as download_file,
        patch(
            "documind.documents.processing.extract_pdf_pages",
        ) as extract_pages,
    ):
        with pytest.raises(EndpointConnectionError) as exception_info:
            asyncio.run(
                extract_stored_document(
                    s3_client=s3_client,
                    bucket="test-documents",
                    storage_key="documents/test-document.pdf",
                )
            )

    assert exception_info.value is error
    download_file.assert_awaited_once()
    extract_pages.assert_not_called()

    temporary_file = download_file.call_args.kwargs["file"]
    assert temporary_file.closed


def test_returns_extracted_pages_and_closes_temporary_file() -> None:
    s3_client = MagicMock()
    expected_pages = [ExtractedPage(page_number=1, text="Document content")]

    async def write_downloaded_content(
        *,
        s3_client: object,
        file: BinaryIO,
        bucket: str,
        storage_key: str,
    ) -> None:
        file.write(b"downloaded PDF content")

    def extract_downloaded_content(file: BinaryIO) -> list[ExtractedPage]:
        assert not file.closed
        file.seek(0)
        assert file.read() == b"downloaded PDF content"
        return expected_pages

    with (
        patch(
            "documind.documents.processing.download_document_file",
            new_callable=AsyncMock,
            side_effect=write_downloaded_content,
        ) as download_file,
        patch(
            "documind.documents.processing.extract_pdf_pages",
            side_effect=extract_downloaded_content,
        ) as extract_pages,
    ):
        pages = asyncio.run(
            extract_stored_document(
                s3_client=s3_client,
                bucket="test-documents",
                storage_key="documents/test-document.pdf",
            )
        )

    temporary_file = download_file.call_args.kwargs["file"]
    download_file.assert_awaited_once_with(
        s3_client=s3_client,
        file=temporary_file,
        bucket="test-documents",
        storage_key="documents/test-document.pdf",
    )
    extract_pages.assert_called_once_with(temporary_file)
    assert pages == expected_pages
    assert temporary_file.closed


@pytest.mark.parametrize(
    "error",
    [
        PdfExtractionError("Could not extract text from the PDF"),
        NoExtractableTextError("The PDF contains no extractable text"),
    ],
)
def test_extraction_failure_closes_temporary_file(error: PdfExtractionError) -> None:
    s3_client = MagicMock()

    with (
        patch(
            "documind.documents.processing.download_document_file",
            new_callable=AsyncMock,
        ) as download_file,
        patch(
            "documind.documents.processing.extract_pdf_pages",
            side_effect=error,
        ) as extract_pages,
    ):
        with pytest.raises(type(error)) as exception_info:
            asyncio.run(
                extract_stored_document(
                    s3_client=s3_client,
                    bucket="test-documents",
                    storage_key="documents/test-document.pdf",
                )
            )

    assert exception_info.value is error
    download_file.assert_awaited_once()
    temporary_file = download_file.call_args.kwargs["file"]
    extract_pages.assert_called_once_with(temporary_file)
    assert temporary_file.closed
