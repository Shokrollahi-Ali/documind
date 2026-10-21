from collections.abc import Callable
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.errors import PyPdfError

from documind.documents.extraction import (
    ExtractedPage,
    NoExtractableTextError,
    PdfExtractionError,
    extract_pdf_pages,
)


def test_extracts_text_and_preserves_original_page_numbers(
    pdf_factory: Callable[[list[bytes]], bytes],
) -> None:
    pdf = pdf_factory(
        [
            b"BT /F1 12 Tf 72 720 Td (  First page  ) Tj ET",
            b"",
            b"BT /F1 12 Tf 72 720 Td (   ) Tj ET",
            b"BT /F1 12 Tf 72 720 Td (Fourth page) Tj ET",
        ]
    )

    with BytesIO(pdf) as file:
        file.seek(10)

        pages = extract_pdf_pages(file)

        assert pages == [
            ExtractedPage(page_number=1, text="First page"),
            ExtractedPage(page_number=4, text="Fourth page"),
        ]
        assert file.tell() == 0
        assert not file.closed


def test_rejects_pdf_without_extractable_text() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        with pytest.raises(NoExtractableTextError):
            extract_pdf_pages(file)

        assert file.tell() == 0
        assert not file.closed


def test_rejects_pdf_with_only_whitespace(pdf_factory: Callable[[list[bytes]], bytes]) -> None:
    pdf = pdf_factory([b"BT /F1 12 Tf 72 720 Td (   ) Tj ET"])

    with BytesIO(pdf) as file:
        with pytest.raises(NoExtractableTextError):
            extract_pdf_pages(file)

        assert file.tell() == 0
        assert not file.closed


def test_rejects_pdf_without_pages(pdf_factory: Callable[[list[bytes]], bytes]) -> None:
    with BytesIO(pdf_factory([])) as file:
        with pytest.raises(NoExtractableTextError):
            extract_pdf_pages(file)

        assert file.tell() == 0
        assert not file.closed


@pytest.mark.parametrize(
    "content",
    [b"", b"This is not a PDF", b"%PDF-1.7\nIncomplete PDF"],
)
def test_wraps_pdf_parsing_errors(content: bytes) -> None:
    with BytesIO(content) as file:
        with pytest.raises(PdfExtractionError) as exception_info:
            extract_pdf_pages(file)

        assert isinstance(exception_info.value.__cause__, PyPdfError)
        assert file.tell() == 0
        assert not file.closed


def test_rejects_encrypted_pdf() -> None:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.encrypt("test-password")
            writer.write(file)

        with pytest.raises(PdfExtractionError, match="Encrypted PDFs are not supported"):
            extract_pdf_pages(file)

        assert file.tell() == 0
        assert not file.closed
