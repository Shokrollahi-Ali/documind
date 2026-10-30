import asyncio
from collections.abc import Callable, Iterator
from time import monotonic, sleep
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.celery import create_celery_app
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.dispatch import dispatch_next_processing_request
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk
from documind.models.document_page import DocumentPage
from documind.models.document_processing_request import DocumentProcessingRequest

pytestmark = pytest.mark.integration


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)) / 100] * 1536 for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FailingEmbeddings(FakeEmbeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ValueError("Invalid embedding response")


@pytest.fixture
def embedding_provider(embedding_failure: bool) -> Iterator[Embeddings]:
    provider = FailingEmbeddings() if embedding_failure else FakeEmbeddings()
    with patch("documind.documents.tasks.create_embeddings", return_value=provider):
        yield provider


@pytest.fixture
def celery_application(
    integration_settings: Settings, embedding_provider: Embeddings
) -> Iterator[Celery]:
    broker_url = integration_settings.celery_broker_url

    if broker_url is None:
        raise ValueError("Integration tests require a test broker URL")

    broker = urlsplit(broker_url.get_secret_value())

    if (
        broker.scheme != "redis"
        or broker.hostname not in {"localhost", "127.0.0.1"}
        or broker.port != 6380
        or broker.path != "/0"
    ):
        raise ValueError("Integration tests require Redis on localhost:6380/0")

    application = create_celery_app(integration_settings)
    queue_name = f"documind-test-{uuid4()}"
    application.conf.task_default_queue = queue_name

    try:
        with start_worker(
            application,
            pool="solo",
            perform_ping_check=False,
            queues=[queue_name],
        ):
            yield application
    finally:
        application.close()


@pytest.mark.parametrize("use_dispatcher", [False, True], ids=["direct", "dispatcher"])
@pytest.mark.parametrize("embedding_failure", [False, True], ids=["ready", "failed"])
def test_worker_extracts_and_saves_uploaded_document(
    use_dispatcher: bool,
    embedding_failure: bool,
    integration_settings: Settings,
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    celery_application: Celery,
    pdf_factory: Callable[[list[bytes]], bytes],
) -> None:
    pdf = pdf_factory(
        [
            b"BT /F1 12 Tf 72 720 Td (First page) Tj ET",
            b"",
            b"BT /F1 12 Tf 72 720 Td (Third page) Tj ET",
        ]
    )

    current_user = authenticated_client.get("/auth/me")
    assert current_user.status_code == 200, current_user.text
    owner_id = current_user.json()["id"]

    upload = authenticated_client.post(
        "/documents",
        files={"file": ("worker-test.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])

    if use_dispatcher:

        async def dispatch_uploaded_document() -> None:
            engine = create_database_engine(integration_settings)
            try:
                session_factory = create_session_factory(engine)
                async with session_factory() as session:
                    assert await dispatch_next_processing_request(session, celery_application)
            finally:
                await engine.dispose()

        asyncio.run(dispatch_uploaded_document())
        with Session(integration_database_engine) as session:
            request = session.scalar(
                select(DocumentProcessingRequest).where(
                    DocumentProcessingRequest.document_id == document_id
                )
            )
            assert request is None
    else:
        celery_application.send_task(
            "documind.process_document",
            args=[str(document_id), owner_id],
            queue=celery_application.conf.task_default_queue,
        )

    deadline = monotonic() + 15

    while monotonic() < deadline:
        with Session(integration_database_engine) as session:
            pages = session.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document_id)
                .order_by(DocumentPage.page_number)
            ).all()

            document = session.get(Document, document_id)

            expected_status = DocumentStatus.FAILED if embedding_failure else DocumentStatus.READY
            if document is not None and document.status == expected_status:
                assert [(page.page_number, page.text) for page in pages] == [
                    (1, "First page"),
                    (3, "Third page"),
                ]
                chunks = session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                ).all()
                assert [(chunk.chunk_index, chunk.page_number, chunk.text) for chunk in chunks] == [
                    (0, 1, "First page"),
                    (1, 3, "Third page"),
                ]
                for chunk in chunks:
                    if embedding_failure:
                        assert chunk.embedding is None
                    else:
                        assert chunk.embedding is not None
                        assert list(chunk.embedding) == pytest.approx(
                            [float(len(chunk.text)) / 100] * 1536
                        )
                assert document.processing_attempt_id is None
                assert document.processing_lease_expires_at is None
                return

        sleep(0.1)

    pytest.fail("The worker did not finish document processing within 15 seconds")
