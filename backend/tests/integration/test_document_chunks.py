from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy import text as sql_text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from documind.models.document import Document
from documind.models.document_chunk import DocumentChunk

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("has_embedding", [False, True])
def test_saves_and_reads_chunk_embedding(
    document_session: tuple[Session, Document],
    has_embedding: bool,
) -> None:
    session, document = document_session
    document_id = document.id
    embedding = [index / 1536 for index in range(1536)] if has_embedding else None

    session.add(
        DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            page_number=1,
            text="A passage to embed",
            embedding=embedding,
        )
    )
    session.flush()
    session.expunge_all()

    stored_chunk = session.get(DocumentChunk, (document_id, 0))

    assert stored_chunk is not None
    if embedding is None:
        assert stored_chunk.embedding is None
    else:
        assert stored_chunk.embedding is not None
        assert list(stored_chunk.embedding) == pytest.approx(embedding)


def test_database_rejects_wrong_embedding_dimensions(
    document_session: tuple[Session, Document],
) -> None:
    session, document = document_session
    document_id = document.id
    session.add(
        DocumentChunk(document_id=document_id, chunk_index=0, page_number=1, text="Passage")
    )
    session.flush()

    with pytest.raises(DBAPIError, match="expected 1536 dimensions"):
        with session.begin_nested():
            session.execute(
                sql_text(
                    "UPDATE document_chunks SET embedding = CAST(:embedding AS vector) "
                    "WHERE document_id = :document_id"
                ),
                {"embedding": "[0.1,0.2]", "document_id": document_id},
            )


def test_saves_and_reads_document_chunks(document_session: tuple[Session, Document]) -> None:
    session, document = document_session
    document_id = document.id
    expected_chunks = [
        (0, 1, "First passage\nSecond line"),
        (1, 1, "Another passage on the same page"),
        (2, 3, "Third page: café"),
    ]
    for chunk_index, page_number, text in reversed(expected_chunks):
        session.add(
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                page_number=page_number,
                text=text,
            )
        )
    session.flush()
    session.expunge_all()

    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()

    assert [
        (chunk.chunk_index, chunk.page_number, chunk.text) for chunk in chunks
    ] == expected_chunks


def test_rejects_duplicate_chunk_index(document_session: tuple[Session, Document]) -> None:
    session, document = document_session
    session.add(
        DocumentChunk(document_id=document.id, chunk_index=0, page_number=1, text="Original")
    )
    session.flush()

    with pytest.raises(IntegrityError, match="pk_document_chunks"):
        with session.begin_nested():
            session.execute(
                insert(DocumentChunk).values(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=2,
                    text="Duplicate index on another page",
                )
            )


@pytest.mark.parametrize(
    ("chunk_index", "page_number", "text", "constraint"),
    [
        (-1, 1, "Text", "ck_document_chunks_nonnegative_chunk_index"),
        (0, 0, "Text", "ck_document_chunks_positive_page_number"),
        (0, -1, "Text", "ck_document_chunks_positive_page_number"),
        (0, 1, "", "ck_document_chunks_nonempty_text"),
    ],
)
def test_rejects_invalid_chunk_values(
    document_session: tuple[Session, Document],
    chunk_index: int,
    page_number: int,
    text: str,
    constraint: str,
) -> None:
    session, document = document_session

    with pytest.raises(IntegrityError, match=constraint):
        with session.begin_nested():
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    text=text,
                )
            )
            session.flush()


def test_rejects_chunk_without_document(document_session: tuple[Session, Document]) -> None:
    session, _ = document_session

    with pytest.raises(IntegrityError, match="fk_document_chunks_document_id_documents"):
        with session.begin_nested():
            session.add(
                DocumentChunk(document_id=uuid4(), chunk_index=0, page_number=1, text="Orphan")
            )
            session.flush()


def test_chunk_indexes_are_scoped_to_each_document(
    document_session: tuple[Session, Document],
) -> None:
    session, document = document_session
    other_document = Document(
        owner_id=document.owner_id,
        original_filename="other.pdf",
        storage_key=f"documents/{uuid4()}.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )
    session.add(other_document)
    session.flush()
    session.add_all(
        [
            DocumentChunk(document_id=document.id, chunk_index=0, page_number=1, text="First"),
            DocumentChunk(
                document_id=other_document.id, chunk_index=0, page_number=1, text="Other"
            ),
        ]
    )
    session.flush()

    session.delete(document)
    session.flush()

    remaining_chunks = session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id.in_([document.id, other_document.id]))
    ).all()

    assert [(chunk.document_id, chunk.text) for chunk in remaining_chunks] == [
        (other_document.id, "Other")
    ]
