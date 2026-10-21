from dataclasses import dataclass
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


class PdfExtractionError(Exception):
    pass


class NoExtractableTextError(PdfExtractionError):
    pass


def extract_pdf_pages(file: BinaryIO) -> list[ExtractedPage]:
    extracted_pages: list[ExtractedPage] = []

    try:
        file.seek(0)
        reader = PdfReader(file, strict=True)

        if reader.is_encrypted:
            raise PdfExtractionError("Encrypted PDFs are not supported")

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text().strip()

            if not text:
                continue

            extracted_pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=text,
                )
            )

    except PyPdfError as error:
        raise PdfExtractionError("Could not extract text from the PDF") from error

    finally:
        file.seek(0)

    if not extracted_pages:
        raise NoExtractableTextError("The PDF contains no extractable text")

    return extracted_pages
