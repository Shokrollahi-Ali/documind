import pytest

from documind.documents.chunking import TextChunk, split_document_pages
from documind.documents.extraction import ExtractedPage


def test_preserves_page_numbers_and_continuous_chunk_indexes() -> None:
    pages = [
        ExtractedPage(page_number=1, text="First page"),
        ExtractedPage(page_number=3, text="Third page"),
    ]

    chunks = split_document_pages(pages, chunk_size=100, chunk_overlap=20)

    assert chunks == [
        TextChunk(chunk_index=0, page_number=1, text="First page"),
        TextChunk(chunk_index=1, page_number=3, text="Third page"),
    ]


def test_splits_long_page_without_losing_page_number() -> None:
    pages = [ExtractedPage(page_number=4, text="alpha beta gamma delta epsilon")]

    chunks = split_document_pages(pages, chunk_size=12, chunk_overlap=3)

    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.page_number == 4 for chunk in chunks)
    assert all(0 < len(chunk.text) <= 12 for chunk in chunks)


def test_returns_no_chunks_for_no_pages() -> None:
    assert split_document_pages([], chunk_size=100, chunk_overlap=20) == []


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)],
)
def test_rejects_invalid_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
    with pytest.raises(ValueError):
        split_document_pages([], chunk_size=chunk_size, chunk_overlap=chunk_overlap)
