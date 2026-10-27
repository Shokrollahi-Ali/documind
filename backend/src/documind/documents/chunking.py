from collections.abc import Sequence
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from documind.documents.extraction import ExtractedPage


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    page_number: int
    text: str


def split_document_pages(
    pages: Sequence[ExtractedPage],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Chunk overlap must be nonnegative and smaller than chunk size")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks: list[TextChunk] = []

    for page in pages:
        for text in splitter.split_text(page.text):
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    page_number=page.page_number,
                    text=text,
                )
            )

    return chunks
