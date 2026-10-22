import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import EndpointConnectionError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.service import create_document
from documind.models.document import DocumentStatus
from documind.models.document_processing_request import DocumentProcessingRequest
from documind.schemas.document_upload import DocumentUploadMetadata


@pytest.fixture
def owner_id() -> UUID:
    return uuid4()


def test_creates_document_and_uploads_file(owner_id: UUID) -> None:
    database_session = MagicMock(spec=AsyncSession)
    s3_client = MagicMock()
    metadata = DocumentUploadMetadata(
        original_filename="document.pdf",
        content_type="application/pdf",
        size_bytes=7,
    )
    transaction_open_during_upload: list[bool] = []

    async def record_upload(**_: object) -> None:
        transaction_open_during_upload.append(database_session.begin.called)

    with BytesIO(b"content") as file:
        with patch(
            "documind.documents.service.upload_document_file",
            new_callable=AsyncMock,
            side_effect=record_upload,
        ) as upload_file:
            document = asyncio.run(
                create_document(
                    owner_id=owner_id,
                    database_session=database_session,
                    s3_client=s3_client,
                    file=file,
                    metadata=metadata,
                    bucket="test-documents",
                )
            )
        upload_file.assert_awaited_once_with(
            s3_client=s3_client,
            file=file,
            bucket="test-documents",
            storage_key=document.storage_key,
            content_type="application/pdf",
        )

    assert transaction_open_during_upload == [False]
    assert database_session.add.call_count == 2
    assert database_session.add.call_args_list[0].args[0] is document

    processing_request = database_session.add.call_args_list[1].args[0]
    assert isinstance(processing_request, DocumentProcessingRequest)
    assert processing_request.document_id == document.id

    assert database_session.flush.await_count == 2

    assert document.owner_id == owner_id
    assert document.original_filename == "document.pdf"
    assert document.content_type == "application/pdf"
    assert document.size_bytes == 7
    assert document.status == DocumentStatus.UPLOADED
    assert document.storage_key == f"documents/{document.id}.pdf"


@pytest.mark.parametrize("failed_insert", [1, 2], ids=["document", "processing-request"])
def test_cleans_up_file_when_database_insert_fails(owner_id: UUID, failed_insert: int) -> None:
    database_session = MagicMock(spec=AsyncSession)
    insert_error = SQLAlchemyError("Database insert failed")
    database_session.flush.side_effect = [None] * (failed_insert - 1) + [insert_error]
    s3_client = MagicMock()
    metadata = DocumentUploadMetadata(
        original_filename="document.pdf",
        content_type="application/pdf",
        size_bytes=7,
    )

    with BytesIO(b"content") as file:
        with (
            patch(
                "documind.documents.service.upload_document_file",
                new_callable=AsyncMock,
            ) as upload_file,
            patch(
                "documind.documents.service.cleanup_uploaded_file",
                new_callable=AsyncMock,
            ) as cleanup_file,
        ):
            with pytest.raises(SQLAlchemyError) as exception_info:
                asyncio.run(
                    create_document(
                        owner_id=owner_id,
                        database_session=database_session,
                        s3_client=s3_client,
                        file=file,
                        metadata=metadata,
                        bucket="test-documents",
                    )
                )

        assert database_session.flush.await_count == failed_insert
        upload_file.assert_awaited_once()
        storage_key = upload_file.call_args.kwargs["storage_key"]
        cleanup_file.assert_awaited_once_with(
            s3_client,
            "test-documents",
            storage_key,
        )
        assert exception_info.value is insert_error


def test_cleans_up_file_when_upload_fails(owner_id: UUID) -> None:
    database_session = MagicMock(spec=AsyncSession)
    s3_client = MagicMock()
    metadata = DocumentUploadMetadata(
        original_filename="document.pdf",
        content_type="application/pdf",
        size_bytes=7,
    )
    upload_error = EndpointConnectionError(endpoint_url="https://s3.example.com")

    with BytesIO(b"content") as file:
        with (
            patch(
                "documind.documents.service.upload_document_file",
                side_effect=upload_error,
            ) as upload_file,
            patch(
                "documind.documents.service.cleanup_uploaded_file",
            ) as cleanup_file,
        ):
            with pytest.raises(EndpointConnectionError) as exception_info:
                asyncio.run(
                    create_document(
                        owner_id=owner_id,
                        database_session=database_session,
                        s3_client=s3_client,
                        file=file,
                        metadata=metadata,
                        bucket="test-documents",
                    )
                )

        upload_file.assert_awaited_once()
        storage_key = upload_file.call_args.kwargs["storage_key"]
        cleanup_file.assert_awaited_once_with(
            s3_client,
            "test-documents",
            storage_key,
        )
        database_session.begin.assert_not_called()
        assert exception_info.value is upload_error


def test_keeps_uploaded_file_when_database_commit_fails(owner_id: UUID) -> None:
    database_session = MagicMock(spec=AsyncSession)
    transaction = database_session.begin.return_value
    commit_error = SQLAlchemyError("Database commit failed")
    transaction.__aexit__.side_effect = commit_error

    s3_client = MagicMock()
    metadata = DocumentUploadMetadata(
        original_filename="document.pdf",
        content_type="application/pdf",
        size_bytes=7,
    )

    with BytesIO(b"content") as file:
        with (
            patch(
                "documind.documents.service.upload_document_file",
            ) as upload_file,
            patch(
                "documind.documents.service.cleanup_uploaded_file",
            ) as cleanup_file,
        ):
            with pytest.raises(SQLAlchemyError) as exception_info:
                asyncio.run(
                    create_document(
                        owner_id=owner_id,
                        database_session=database_session,
                        s3_client=s3_client,
                        file=file,
                        metadata=metadata,
                        bucket="test-documents",
                    )
                )

        upload_file.assert_awaited_once()
        transaction.__aexit__.assert_awaited_once_with(None, None, None)
        cleanup_file.assert_not_called()
        assert exception_info.value is commit_error


def test_preserves_upload_error_when_cleanup_fails(
    caplog: pytest.LogCaptureFixture,
    owner_id: UUID,
) -> None:
    database_session = MagicMock(spec=AsyncSession)
    s3_client = MagicMock()
    metadata = DocumentUploadMetadata(
        original_filename="document.pdf",
        content_type="application/pdf",
        size_bytes=7,
    )
    upload_error = EndpointConnectionError(endpoint_url="https://upload.example.com")
    cleanup_error = EndpointConnectionError(endpoint_url="https://cleanup.example.com")

    with BytesIO(b"content") as file:
        with (
            patch(
                "documind.documents.service.upload_document_file",
                side_effect=upload_error,
            ) as upload_file,
            patch(
                "documind.documents.service.delete_document_file",
                side_effect=cleanup_error,
            ) as delete_file,
        ):
            with pytest.raises(EndpointConnectionError) as exception_info:
                asyncio.run(
                    create_document(
                        owner_id=owner_id,
                        database_session=database_session,
                        s3_client=s3_client,
                        file=file,
                        metadata=metadata,
                        bucket="test-documents",
                    )
                )

        storage_key = upload_file.call_args.kwargs["storage_key"]
        delete_file.assert_awaited_once_with(
            s3_client=s3_client,
            bucket="test-documents",
            storage_key=storage_key,
        )
        assert exception_info.value is upload_error

    assert "Failed to delete uploaded file during cleanup" in caplog.text
    assert storage_key in caplog.text
