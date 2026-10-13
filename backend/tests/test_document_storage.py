import asyncio
from io import BytesIO
from unittest.mock import MagicMock

from documind.storage.s3 import delete_document_file, upload_document_file


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
