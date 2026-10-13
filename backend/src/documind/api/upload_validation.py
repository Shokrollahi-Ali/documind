from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from starlette.concurrency import run_in_threadpool

from documind.core.config import Settings
from documind.schemas.document_upload import DocumentUploadMetadata


def validate_pdf_filename(filename: str | None) -> str:
    if filename is None or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A filename is required"
        )
    if len(filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename must not exceed 255 characters",
        )
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported",
        )
    return filename


def validate_upload_size(file: BinaryIO, max_size_bytes: int) -> int:
    file.seek(0, 2)
    size_bytes = file.tell()
    file.seek(0)
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The uploaded file is empty"
        )
    if size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File must not exceed {max_size_bytes} bytes",
        )
    return size_bytes


def validate_pdf_content(file: BinaryIO) -> None:
    try:
        file.seek(0)
        reader = PdfReader(file, strict=True)
        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Encrypted PDFs are not supported",
            )
        if len(reader.pages) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The PDF must contain at least one page",
            )
    except PyPdfError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file could not be read as a valid PDF",
        ) from error
    finally:
        file.seek(0)


async def validate_document_upload(
    upload: UploadFile, settings: Settings
) -> DocumentUploadMetadata:
    filename = validate_pdf_filename(upload.filename)

    if upload.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The file content type must be application/pdf",
        )

    size_bytes = await run_in_threadpool(
        validate_upload_size, upload.file, settings.max_upload_size_bytes
    )

    await run_in_threadpool(validate_pdf_content, upload.file)

    return DocumentUploadMetadata(
        original_filename=filename,
        content_type="application/pdf",
        size_bytes=size_bytes,
    )
