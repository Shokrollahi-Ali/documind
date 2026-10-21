import asyncio
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from documind.storage.s3 import (
    delete_document_file,
    download_document_file,
    upload_document_file,
)


def test_upload_passes_file_and_metadata_to_s3() -> None:
    s3_client = MagicMock(spec=["upload_fileobj"])

    with BytesIO(b"document content") as file:
        asyncio.run(
            upload_document_file(
                s3_client=s3_client,
                file=file,
                bucket="test-documents",
                storage_key="documents/test-document.pdf",
                content_type="application/pdf",
            )
        )

        s3_client.upload_fileobj.assert_called_once_with(
            Fileobj=file,
            Bucket="test-documents",
            Key="documents/test-document.pdf",
            ExtraArgs={"ContentType": "application/pdf"},
        )


def test_delete_passes_bucket_and_storage_key_to_s3() -> None:
    s3_client = MagicMock(spec=["delete_object"])

    asyncio.run(
        delete_document_file(
            s3_client=s3_client,
            bucket="test-documents",
            storage_key="documents/test-document.pdf",
        )
    )

    s3_client.delete_object.assert_called_once_with(
        Bucket="test-documents",
        Key="documents/test-document.pdf",
    )


def test_download_passes_file_and_storage_key_to_s3() -> None:
    s3_client = MagicMock(spec=["download_fileobj"])

    with BytesIO() as file:
        asyncio.run(
            download_document_file(
                s3_client=s3_client,
                file=file,
                bucket="test-documents",
                storage_key="documents/test-document.pdf",
            )
        )

        s3_client.download_fileobj.assert_called_once_with(
            Bucket="test-documents",
            Key="documents/test-document.pdf",
            Fileobj=file,
        )
        assert not file.closed


def test_download_propagates_storage_errors() -> None:
    s3_client = MagicMock(spec=["download_fileobj"])
    error = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Document not found"}},
        "GetObject",
    )
    s3_client.download_fileobj.side_effect = error

    with BytesIO() as file:
        with pytest.raises(ClientError) as exception_info:
            asyncio.run(
                download_document_file(
                    s3_client=s3_client,
                    file=file,
                    bucket="test-documents",
                    storage_key="documents/missing-document.pdf",
                )
            )

        assert exception_info.value is error
        assert not file.closed
