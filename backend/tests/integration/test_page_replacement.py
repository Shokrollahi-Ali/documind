import asyncio
from collections.abc import Iterator, Sequence
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.extraction import ExtractedPage
from documind.documents.pages import replace_document_pages
from documind.models.document import Document, DocumentStatus
from documind.models.document_page import DocumentPage
from documind.models.user import User

pytestmark = pytest.mark.integration


@pytest.fixture
def stored_document(integration_database_engine: Engine) -> Iterator[tuple[UUID, UUID]]:
    user_id = uuid4()
    document_id = uuid4()

    with Session(integration_database_engine) as session:
        with session.begin():
            session.add(
                User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    password_hash="unused-in-page-replacement-tests",
                )
            )
            session.flush()
            session.add(
                Document(
                    id=document_id,
                    owner_id=user_id,
                    original_filename="document.pdf",
                    storage_key=f"documents/{document_id}.pdf",
                    content_type="application/pdf",
                    size_bytes=100,
                )
            )

    try:
        yield document_id, user_id
    finally:
        with Session(integration_database_engine) as session:
            with session.begin():
                session.execute(delete(Document).where(Document.id == document_id))
                session.execute(delete(User).where(User.id == user_id))


async def save_pages(
    settings: Settings,
    document_id: UUID,
    owner_id: UUID,
    pages: Sequence[ExtractedPage],
) -> bool:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        attempt_id = uuid4()

        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(Document)
                    .where(
                        Document.id == document_id,
                        Document.owner_id == owner_id,
                    )
                    .values(
                        status=DocumentStatus.PROCESSING,
                        processing_attempt_id=attempt_id,
                        processing_lease_expires_at=(func.clock_timestamp() + timedelta(minutes=5)),
                    )
                )

        async with session_factory() as session:
            return await replace_document_pages(
                database_session=session,
                document_id=document_id,
                owner_id=owner_id,
                pages=pages,
                attempt_id=attempt_id,
            )
    finally:
        await engine.dispose()


def read_pages(engine: Engine, document_id: UUID) -> list[ExtractedPage]:
    with Session(engine) as session:
        pages = session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        ).all()
        return [ExtractedPage(page_number=page.page_number, text=page.text) for page in pages]


def test_saves_and_replaces_pages_without_duplicates(
    integration_settings: Settings,
    integration_database_engine: Engine,
    stored_document: tuple[UUID, UUID],
) -> None:
    document_id, owner_id = stored_document
    original_pages = [ExtractedPage(1, "Original text"), ExtractedPage(2, "Old second page")]
    replacement_pages = [ExtractedPage(1, "Updated text"), ExtractedPage(3, "New third page")]

    for pages in [original_pages, replacement_pages, replacement_pages]:
        saved = asyncio.run(save_pages(integration_settings, document_id, owner_id, pages))

        assert saved is True
        assert read_pages(integration_database_engine, document_id) == pages
        with Session(integration_database_engine) as session:
            document = session.get(Document, document_id)
            assert document is not None
            assert document.status == DocumentStatus.EXTRACTED


@pytest.mark.parametrize("missing_document", [False, True], ids=["wrong-owner", "missing-document"])
def test_rejects_inaccessible_document_without_changing_pages(
    integration_settings: Settings,
    integration_database_engine: Engine,
    stored_document: tuple[UUID, UUID],
    missing_document: bool,
) -> None:
    document_id, owner_id = stored_document
    original_pages = [ExtractedPage(1, "Original text")]
    asyncio.run(save_pages(integration_settings, document_id, owner_id, original_pages))
    requested_document_id = uuid4() if missing_document else document_id
    requested_owner_id = owner_id if missing_document else uuid4()

    saved = asyncio.run(
        save_pages(
            integration_settings,
            requested_document_id,
            requested_owner_id,
            [ExtractedPage(1, "Replacement text")],
        )
    )

    assert saved is False
    assert read_pages(integration_database_engine, document_id) == original_pages


@pytest.mark.parametrize(
    "invalid_pages",
    [
        [ExtractedPage(1, "Duplicate one"), ExtractedPage(1, "Duplicate two")],
        [ExtractedPage(1, "Valid page"), ExtractedPage(0, "Invalid page number")],
        [ExtractedPage(1, "Valid page"), ExtractedPage(2, "")],
    ],
    ids=["duplicate-page", "invalid-page-number", "empty-text"],
)
def test_failed_replacement_preserves_previous_pages(
    integration_settings: Settings,
    integration_database_engine: Engine,
    stored_document: tuple[UUID, UUID],
    invalid_pages: list[ExtractedPage],
) -> None:
    document_id, owner_id = stored_document
    original_pages = [ExtractedPage(1, "Original text"), ExtractedPage(2, "Second page")]
    asyncio.run(save_pages(integration_settings, document_id, owner_id, original_pages))

    with Session(integration_database_engine) as session:
        with session.begin():
            document = session.get(Document, document_id)
            assert document is not None
            document.status = DocumentStatus.PROCESSING

    with pytest.raises(IntegrityError):
        asyncio.run(save_pages(integration_settings, document_id, owner_id, invalid_pages))

    assert read_pages(integration_database_engine, document_id) == original_pages
    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING


@pytest.mark.parametrize("lease_expired", [False, True], ids=["replaced", "expired"])
def test_stale_attempt_does_not_replace_pages(
    integration_settings: Settings,
    integration_database_engine: Engine,
    stored_document: tuple[UUID, UUID],
    lease_expired: bool,
) -> None:
    document_id, owner_id = stored_document
    original_pages = [ExtractedPage(1, "Original text")]
    asyncio.run(save_pages(integration_settings, document_id, owner_id, original_pages))

    stale_attempt_id = uuid4()
    current_attempt_id = uuid4() if not lease_expired else stale_attempt_id

    with Session(integration_database_engine) as session:
        with session.begin():
            document = session.get(Document, document_id)
            assert document is not None
            database_time = session.scalar(select(func.clock_timestamp()))
            assert database_time is not None

            document.status = DocumentStatus.PROCESSING
            document.processing_attempt_id = current_attempt_id
            document.processing_lease_expires_at = database_time + timedelta(
                seconds=-1 if lease_expired else 300
            )
            original_expiry = document.processing_lease_expires_at

    async def attempt_replacement() -> bool:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                return await replace_document_pages(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    pages=[ExtractedPage(1, "Stale text")],
                    attempt_id=stale_attempt_id,
                )
        finally:
            await engine.dispose()

    assert asyncio.run(attempt_replacement()) is False
    assert read_pages(integration_database_engine, document_id) == original_pages

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING
        assert document.processing_attempt_id == current_attempt_id
        assert document.processing_lease_expires_at == original_expiry
