import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from pypdf import PdfWriter
from starlette.datastructures import Headers

from documind.api.upload_validation import (
    validate_document_upload,
    validate_pdf_content,
    validate_pdf_filename,
    validate_upload_size,
)
from documind.core.config import Settings


@pytest.mark.parametrize("filename", ["document.pdf", "document.PDF", "a" * 251 + ".pdf"])
def test_accepts_valid_pdf_filename(filename: str) -> None:
    assert validate_pdf_filename(filename) == filename


@pytest.mark.parametrize(
    ("filename", "expected_status", "expected_detail"),
    [
        (None, 422, "A filename is required"),
        ("", 422, "A filename is required"),
        ("   ", 422, "A filename is required"),
        (
            "a" * 252 + ".pdf",
            422,
            "Filename must not exceed 255 characters",
        ),
        ("docu\x00ment.pdf", 422, "Filename must not contain null characters"),
        ("document.txt", 415, "Only PDF files are supported"),
        ("document.pdf.exe", 415, "Only PDF files are supported"),
    ],
)
def test_rejects_invalid_pdf_filename(
    filename: str | None, expected_status: int, expected_detail: str
) -> None:
    with pytest.raises(HTTPException) as exception_info:
        validate_pdf_filename(filename)

    assert exception_info.value.status_code == expected_status
    assert exception_info.value.detail == expected_detail


@pytest.mark.parametrize("size_bytes", [1, 10])
def test_accepts_valid_file_size(size_bytes: int) -> None:
    with BytesIO(b"a" * size_bytes) as file:
        file.seek(1)
        file_size = validate_upload_size(file, max_size_bytes=10)

        assert file_size == size_bytes
        assert file.tell() == 0


@pytest.mark.parametrize(
    ("size_bytes", "expected_status", "expected_detail"),
    [
        (0, 422, "The uploaded file is empty"),
        (11, 413, "File must not exceed 10 bytes"),
    ],
)
def test_rejects_not_valid_file_size(
    size_bytes: int, expected_status: int, expected_detail: str
) -> None:
    with BytesIO(b"a" * size_bytes) as file:
        with pytest.raises(HTTPException) as exception_info:
            file.seek(1)
            validate_upload_size(file, max_size_bytes=10)
        assert exception_info.value.status_code == expected_status
        assert exception_info.value.detail == expected_detail
        assert file.tell() == 0


def test_accepts_valid_pdf_content() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        validate_pdf_content(file)
        assert file.tell() == 0


@pytest.mark.parametrize(
    "content",
    [
        b"This is not a PDF",
        b"%PDF-1.7\nThis file has a PDF header but no valid structure",
    ],
)
def test_rejects_invalid_pdf_content(content: bytes) -> None:
    with BytesIO(content) as file:
        with pytest.raises(HTTPException) as exception_info:
            validate_pdf_content(file)

        assert exception_info.value.status_code == 422
        assert exception_info.value.detail == ("The uploaded file could not be read as a valid PDF")
        assert file.tell() == 0


def test_rejects_encrypted_pdf_content() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.encrypt("test-password")
            writer.write(file)

        with pytest.raises(HTTPException) as exception_info:
            validate_pdf_content(file)

        assert exception_info.value.status_code == 422
        assert exception_info.value.detail == "Encrypted PDFs are not supported"
        assert file.tell() == 0


def test_rejects_pdf_without_pages() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.write(file)

        with pytest.raises(HTTPException) as exception_info:
            validate_pdf_content(file)

        assert exception_info.value.status_code == 422
        assert exception_info.value.detail == ("The PDF must contain at least one page")
        assert file.tell() == 0


def test_returns_validated_upload_metadata() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        size_bytes = file.tell()
        file.seek(0)

        upload = UploadFile(
            file=file,
            filename="document.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )

        settings = Settings(max_upload_size_bytes=size_bytes)
        metadata = asyncio.run(validate_document_upload(upload, settings))
        assert metadata.original_filename == "document.pdf"
        assert metadata.content_type == "application/pdf"
        assert metadata.size_bytes == size_bytes
        assert file.tell() == 0


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/octet-stream", None],
)
def test_rejects_upload_with_unsupported_content_type(content_type: str | None) -> None:
    headers = Headers({"content_type": content_type} if content_type is not None else {})
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        file.seek(0)
        upload = UploadFile(
            file=file,
            filename="document.pdf",
            headers=headers,
        )
        settings = Settings(max_upload_size_bytes=1024 * 1024)

        with pytest.raises(HTTPException) as exception_info:
            asyncio.run(validate_document_upload(upload, settings))

        assert exception_info.value.status_code == 415
        assert exception_info.value.detail == "The file content type must be application/pdf"


def test_rejects_upload_exceeding_configured_size_limit() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        size_bytes = file.tell()
        file.seek(0)

        upload = UploadFile(
            file=file,
            filename="document.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )
        max_size_bytes = size_bytes - 1
        settings = Settings(max_upload_size_bytes=max_size_bytes)

        with pytest.raises(HTTPException) as exception_info:
            asyncio.run(validate_document_upload(upload, settings))

        assert exception_info.value.status_code == 413
        assert exception_info.value.detail == (f"File must not exceed {max_size_bytes} bytes")
        assert file.tell() == 0
