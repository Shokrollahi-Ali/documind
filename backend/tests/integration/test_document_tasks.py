from collections.abc import Callable, Iterator
from time import monotonic, sleep
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.celery import create_celery_app
from documind.core.config import Settings
from documind.models.document_page import DocumentPage

pytestmark = pytest.mark.integration


@pytest.fixture
def celery_application(integration_settings: Settings) -> Iterator[Celery]:
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


def test_worker_extracts_and_saves_uploaded_document(
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

            if pages:
                assert [(page.page_number, page.text) for page in pages] == [
                    (1, "First page"),
                    (3, "Third page"),
                ]
                return

        sleep(0.1)

    pytest.fail("The worker did not save document pages within 15 seconds")
