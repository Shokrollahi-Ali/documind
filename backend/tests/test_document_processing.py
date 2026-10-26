import asyncio
from typing import BinaryIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import EndpointConnectionError

from documind.documents.extraction import (
    ExtractedPage,
    NoExtractableTextError,
    PdfExtractionError,
)
from documind.documents.lease_heartbeat import ProcessingLeaseLostError
from documind.documents.processing import (
    extract_and_store_document_pages,
    extract_stored_document,
    extract_with_lease_renewal,
)
from documind.models.document import Document, DocumentStatus


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


def test_inaccessible_document_skips_extraction_and_storage() -> None:
    session_factory = MagicMock()
    s3_client = MagicMock()
    document_id = uuid4()
    owner_id = uuid4()

    with (
        patch(
            "documind.documents.processing.get_document",
            new_callable=AsyncMock,
            return_value=None,
        ) as get_document,
        patch(
            "documind.documents.processing.extract_stored_document",
            new_callable=AsyncMock,
        ) as extract_document,
        patch(
            "documind.documents.processing.replace_document_pages",
            new_callable=AsyncMock,
        ) as replace_pages,
    ):
        saved = asyncio.run(
            extract_and_store_document_pages(
                session_factory=session_factory,
                s3_client=s3_client,
                bucket="test-documents",
                document_id=document_id,
                owner_id=owner_id,
                lease_seconds=300,
            )
        )

    assert saved is False
    session_factory.assert_called_once_with()
    get_document.assert_awaited_once_with(
        database_session=session_factory.return_value.__aenter__.return_value,
        document_id=document_id,
        owner_id=owner_id,
    )
    extract_document.assert_not_awaited()
    replace_pages.assert_not_awaited()


def test_extraction_stops_before_saving_when_lease_is_lost() -> None:
    document_id = uuid4()
    lease_error = ProcessingLeaseLostError(f"Processing lease lost for document {document_id}")

    async def finish_extraction(**kwargs: object) -> list[ExtractedPage]:
        await asyncio.sleep(0)
        return [ExtractedPage(page_number=1, text="Extracted text")]

    with (
        patch(
            "documind.documents.processing.maintain_processing_lease",
            new_callable=AsyncMock,
            side_effect=lease_error,
        ),
        patch(
            "documind.documents.processing.extract_stored_document",
            new_callable=AsyncMock,
            side_effect=finish_extraction,
        ),
    ):
        with pytest.raises(ProcessingLeaseLostError) as exception_info:
            asyncio.run(
                extract_with_lease_renewal(
                    session_factory=MagicMock(),
                    s3_client=MagicMock(),
                    bucket="test-documents",
                    storage_key="documents/test-document.pdf",
                    document_id=document_id,
                    owner_id=uuid4(),
                    attempt_id=uuid4(),
                    lease_seconds=300,
                )
            )

    assert exception_info.value is lease_error


def test_extraction_failure_stops_lease_heartbeat() -> None:
    heartbeat_started = asyncio.Event()
    heartbeat_stopped = asyncio.Event()
    extraction_error = PdfExtractionError("Could not extract text from the PDF")

    async def maintain_lease(**kwargs: object) -> None:
        heartbeat_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            heartbeat_stopped.set()

    async def fail_extraction(**kwargs: object) -> list[ExtractedPage]:
        await heartbeat_started.wait()
        raise extraction_error

    with (
        patch(
            "documind.documents.processing.maintain_processing_lease",
            new_callable=AsyncMock,
            side_effect=maintain_lease,
        ),
        patch(
            "documind.documents.processing.extract_stored_document",
            new_callable=AsyncMock,
            side_effect=fail_extraction,
        ),
    ):
        with pytest.raises(PdfExtractionError) as exception_info:
            asyncio.run(
                extract_with_lease_renewal(
                    session_factory=MagicMock(),
                    s3_client=MagicMock(),
                    bucket="test-documents",
                    storage_key="documents/test-document.pdf",
                    document_id=uuid4(),
                    owner_id=uuid4(),
                    attempt_id=uuid4(),
                    lease_seconds=300,
                )
            )

    assert exception_info.value is extraction_error
    assert heartbeat_stopped.is_set()


def test_document_without_a_lease_skips_extraction() -> None:
    session_factory = MagicMock()
    document = Document(
        id=uuid4(),
        owner_id=uuid4(),
        status=DocumentStatus.UPLOADED,
        storage_key="documents/test-document.pdf",
    )

    with (
        patch(
            "documind.documents.processing.get_document",
            new_callable=AsyncMock,
            return_value=document,
        ),
        patch(
            "documind.documents.processing.claim_document_processing",
            new_callable=AsyncMock,
            return_value=None,
        ) as claim,
        patch(
            "documind.documents.processing.extract_with_lease_renewal",
            new_callable=AsyncMock,
        ) as extract,
        patch(
            "documind.documents.processing.replace_document_pages",
            new_callable=AsyncMock,
        ) as replace_pages,
    ):
        saved = asyncio.run(
            extract_and_store_document_pages(
                session_factory=session_factory,
                s3_client=MagicMock(),
                bucket="test-documents",
                document_id=document.id,
                owner_id=document.owner_id,
                lease_seconds=300,
            )
        )

    assert saved is False
    claim.assert_awaited_once()
    extract.assert_not_awaited()
    replace_pages.assert_not_awaited()


@pytest.mark.parametrize("status", [DocumentStatus.EXTRACTED, DocumentStatus.READY])
def test_completed_document_skips_extraction_and_storage(status: DocumentStatus) -> None:
    session_factory = MagicMock()
    document = Document(id=uuid4(), owner_id=uuid4(), status=status)

    with (
        patch(
            "documind.documents.processing.get_document",
            new_callable=AsyncMock,
            return_value=document,
        ) as get_document,
        patch(
            "documind.documents.processing.extract_stored_document",
            new_callable=AsyncMock,
        ) as extract_document,
        patch(
            "documind.documents.processing.replace_document_pages",
            new_callable=AsyncMock,
        ) as replace_pages,
    ):
        saved = asyncio.run(
            extract_and_store_document_pages(
                session_factory=session_factory,
                s3_client=MagicMock(),
                bucket="test-documents",
                document_id=document.id,
                owner_id=document.owner_id,
                lease_seconds=300,
            )
        )

    assert saved is True
    assert document.status == status
    session_factory.assert_called_once_with()
    get_document.assert_awaited_once_with(
        database_session=session_factory.return_value.__aenter__.return_value,
        document_id=document.id,
        owner_id=document.owner_id,
    )
    extract_document.assert_not_awaited()
    replace_pages.assert_not_awaited()
