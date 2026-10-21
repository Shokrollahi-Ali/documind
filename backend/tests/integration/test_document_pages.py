from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from documind.models.document import Document
from documind.models.document_page import DocumentPage
from documind.models.user import User

pytestmark = pytest.mark.integration


@pytest.fixture
def document_session(
    integration_database_engine: Engine,
) -> Iterator[tuple[Session, Document]]:
    with Session(integration_database_engine) as session:
        user = User(
            email=f"{uuid4()}@example.com",
            password_hash="unused-in-document-page-tests",
        )
        session.add(user)
        session.flush()

        document = Document(
            owner_id=user.id,
            original_filename="document.pdf",
            storage_key=f"documents/{uuid4()}.pdf",
            content_type="application/pdf",
            size_bytes=100,
        )
        session.add(document)
        session.flush()

        yield session, document


def test_saves_and_reads_document_pages(document_session: tuple[Session, Document]) -> None:
    session, document = document_session
    document_id = document.id
    expected_pages = [(1, "First page\nSecond line"), (3, "Third page: café")]
    session.add_all(
        DocumentPage(document_id=document_id, page_number=page_number, text=text)
        for page_number, text in expected_pages
    )
    session.flush()
    session.expunge_all()

    pages = session.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    ).all()

    assert [(page.page_number, page.text) for page in pages] == expected_pages


def test_rejects_duplicate_document_page(document_session: tuple[Session, Document]) -> None:
    session, document = document_session
    session.add(DocumentPage(document_id=document.id, page_number=1, text="Original text"))
    session.flush()

    with pytest.raises(IntegrityError, match="pk_document_pages"):
        with session.begin_nested():
            session.execute(
                insert(DocumentPage).values(
                    document_id=document.id,
                    page_number=1,
                    text="Duplicate text",
                )
            )


@pytest.mark.parametrize(
    ("page_number", "text", "constraint"),
    [
        (0, "Page text", "ck_document_pages_positive_page_number"),
        (-1, "Page text", "ck_document_pages_positive_page_number"),
        (1, "", "ck_document_pages_nonempty_text"),
    ],
)
def test_rejects_invalid_page_values(
    document_session: tuple[Session, Document],
    page_number: int,
    text: str,
    constraint: str,
) -> None:
    session, document = document_session

    with pytest.raises(IntegrityError, match=constraint):
        with session.begin_nested():
            session.add(DocumentPage(document_id=document.id, page_number=page_number, text=text))
            session.flush()


def test_rejects_page_without_document(document_session: tuple[Session, Document]) -> None:
    session, _ = document_session

    with pytest.raises(IntegrityError, match="fk_document_pages_document_id_documents"):
        with session.begin_nested():
            session.add(DocumentPage(document_id=uuid4(), page_number=1, text="Orphan page"))
            session.flush()


def test_deleting_document_removes_its_pages(document_session: tuple[Session, Document]) -> None:
    session, document = document_session
    document_id = document.id
    session.add_all(
        [
            DocumentPage(document_id=document_id, page_number=1, text="First page"),
            DocumentPage(document_id=document_id, page_number=2, text="Second page"),
        ]
    )
    session.flush()

    session.delete(document)
    session.flush()

    remaining_pages = session.scalars(
        select(DocumentPage).where(DocumentPage.document_id == document_id)
    ).all()

    assert remaining_pages == []
