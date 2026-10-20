import asyncio
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import EndpointConnectionError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.service import delete_document
from documind.models.document import Document, DocumentStatus


@pytest.fixture
def owner_id() -> UUID:
    return uuid4()


def test_deletes_stored_file_and_database_record(owner_id: UUID) -> None:
    document_id = uuid4()
    document = Document(
        id=document_id,
        owner_id=owner_id,
        original_filename="document.pdf",
        storage_key=f"documents/{document_id}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
    )
    database_session = MagicMock(spec=AsyncSession)
    documents = MagicMock()
    documents.one_or_none.return_value = document
    database_session.scalars.return_value = documents
    s3_client = MagicMock()
    transaction = database_session.begin.return_value
    committed_before_file_deletion: list[bool] = []

    async def record_file_deletion(**_: object) -> None:
        committed_before_file_deletion.append(transaction.__aexit__.called)

    with patch(
        "documind.documents.service.delete_document_file",
        side_effect=record_file_deletion,
    ) as delete_file:
        deleted = asyncio.run(
            delete_document(
                owner_id=owner_id,
                database_session=database_session,
                s3_client=s3_client,
                document_id=document_id,
                bucket="test-documents",
            )
        )

    assert deleted is True
    database_session.scalars.assert_awaited_once()
    database_session.delete.assert_awaited_once_with(document)
    transaction.__aexit__.assert_awaited_once_with(None, None, None)
    delete_file.assert_awaited_once_with(
        s3_client=s3_client,
        bucket="test-documents",
        storage_key=document.storage_key,
    )
    assert committed_before_file_deletion == [True]


def test_returns_false_when_document_does_not_exist(owner_id: UUID) -> None:
    document_id = uuid4()
    database_session = MagicMock(spec=AsyncSession)
    documents = MagicMock()
    documents.one_or_none.return_value = None
    database_session.scalars.return_value = documents
    s3_client = MagicMock()

    with patch("documind.documents.service.delete_document_file") as delete_file:
        deleted = asyncio.run(
            delete_document(
                owner_id=owner_id,
                database_session=database_session,
                s3_client=s3_client,
                document_id=document_id,
                bucket="test-documents",
            )
        )

    assert deleted is False
    database_session.scalars.assert_awaited_once()
    delete_file.assert_not_called()
    database_session.delete.assert_not_called()


def test_keeps_database_deletion_when_storage_deletion_fails(
    caplog: pytest.LogCaptureFixture,
    owner_id: UUID,
) -> None:
    document_id = uuid4()
    document = Document(
        id=document_id,
        owner_id=owner_id,
        original_filename="document.pdf",
        storage_key=f"documents/{document_id}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
    )
    database_session = MagicMock(spec=AsyncSession)
    documents = MagicMock()
    documents.one_or_none.return_value = document
    database_session.scalars.return_value = documents
    s3_client = MagicMock()
    storage_error = EndpointConnectionError(endpoint_url="https://s3.example.com")

    with patch(
        "documind.documents.service.delete_document_file",
        side_effect=storage_error,
    ) as delete_file:
        deleted = asyncio.run(
            delete_document(
                owner_id=owner_id,
                database_session=database_session,
                s3_client=s3_client,
                document_id=document_id,
                bucket="test-documents",
            )
        )

    assert deleted is True
    database_session.delete.assert_awaited_once_with(document)
    transaction = database_session.begin.return_value
    transaction.__aexit__.assert_awaited_once_with(None, None, None)
    delete_file.assert_awaited_once_with(
        s3_client=s3_client,
        bucket="test-documents",
        storage_key=document.storage_key,
    )
    assert "Failed to delete stored file after deleting document" in caplog.text
    assert document.storage_key in caplog.text


def test_keeps_stored_file_when_database_commit_fails(owner_id: UUID) -> None:
    document_id = uuid4()
    document = Document(
        id=document_id,
        owner_id=owner_id,
        original_filename="document.pdf",
        storage_key=f"documents/{document_id}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
    )
    database_session = MagicMock(spec=AsyncSession)
    documents = MagicMock()
    documents.one_or_none.return_value = document
    database_session.scalars.return_value = documents
    s3_client = MagicMock()

    database_error = SQLAlchemyError("Database commit failed")
    transaction = database_session.begin.return_value
    transaction.__aexit__.side_effect = database_error

    with patch("documind.documents.service.delete_document_file") as delete_file:
        with pytest.raises(SQLAlchemyError) as exception_info:
            asyncio.run(
                delete_document(
                    owner_id=owner_id,
                    database_session=database_session,
                    s3_client=s3_client,
                    document_id=document_id,
                    bucket="test-documents",
                )
            )

    assert exception_info.value is database_error
    delete_file.assert_not_called()
    database_session.delete.assert_awaited_once_with(document)
    transaction.__aexit__.assert_awaited_once_with(None, None, None)
