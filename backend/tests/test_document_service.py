import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import EndpointConnectionError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.service import create_document
from documind.models.document import DocumentStatus
from documind.schemas.document_upload import DocumentUploadMetadata


def test_creates_document_and_uploads_file() -> None:
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
    database_session.add.assert_called_once_with(document)
    database_session.flush.assert_awaited_once_with()

    assert document.original_filename == "document.pdf"
    assert document.content_type == "application/pdf"
    assert document.size_bytes == 7
    assert document.status == DocumentStatus.UPLOADED
    assert document.storage_key == f"documents/{document.id}.pdf"


def test_cleans_up_file_when_database_insert_fails() -> None:
    database_session = MagicMock(spec=AsyncSession)
    insert_error = SQLAlchemyError("Database insert failed")
    database_session.flush.side_effect = insert_error
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
                        database_session=database_session,
                        s3_client=s3_client,
                        file=file,
                        metadata=metadata,
                        bucket="test-documents",
                    )
                )

        database_session.flush.assert_awaited_once_with()
        upload_file.assert_awaited_once()
        storage_key = upload_file.call_args.kwargs["storage_key"]
        cleanup_file.assert_awaited_once_with(
            s3_client,
            "test-documents",
            storage_key,
        )
        assert exception_info.value is insert_error


def test_cleans_up_file_when_upload_fails() -> None:
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


def test_keeps_uploaded_file_when_database_commit_fails() -> None:
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
