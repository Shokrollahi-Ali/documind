from collections.abc import Callable, Iterator
from contextlib import ExitStack, closing
from io import BytesIO
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.main import create_app
from documind.models.document import Document
from documind.models.user import User
from documind.storage.s3 import create_s3_client

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    settings = Settings(_env_file=None)
    database_url = make_url(settings.database_url.get_secret_value())

    if settings.environment != "test":
        raise ValueError("Integration tests require the test environment")

    if database_url.database != "documind_test":
        raise ValueError("Integration tests require the documind_test database")

    if settings.s3_bucket != "documind-documents-test":
        raise ValueError("Integration tests require the documind-documents-test bucket")

    if settings.s3_endpoint_url is None:
        raise ValueError("Integration tests require a LocalStack endpoint")

    return settings


@pytest.fixture
def integration_client(
    integration_settings: Settings,
) -> Iterator[TestClient]:
    application = create_app(integration_settings)

    with TestClient(application) as client:
        yield client


@pytest.fixture
def integration_database_engine(
    integration_settings: Settings,
) -> Iterator[Engine]:
    engine = create_engine(
        integration_settings.database_url.get_secret_value(),
    )

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def document_session(
    integration_database_engine: Engine,
) -> Iterator[tuple[Session, Document]]:
    with Session(integration_database_engine) as session:
        user = User(
            email=f"{uuid4()}@example.com",
            password_hash="unused-in-document-storage-tests",
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


@pytest.fixture
def integration_s3_client(
    integration_settings: Settings,
) -> Iterator["S3Client"]:
    with closing(create_s3_client(integration_settings)) as client:
        yield client


@pytest.fixture
def authenticated_client_factory(
    integration_settings: Settings,
    integration_database_engine: Engine,
    integration_s3_client: "S3Client",
) -> Iterator[Callable[[], TestClient]]:
    user_ids: list[UUID] = []

    with ExitStack() as clients:

        def create_authenticated_client() -> TestClient:
            client = clients.enter_context(TestClient(create_app(integration_settings)))
            credentials = {
                "email": f"document-test-{uuid4()}@example.com",
                "password": "document-integration-test-password",
            }
            registration = client.post("/auth/register", json=credentials)
            assert registration.status_code == 201, registration.text
            user_ids.append(UUID(registration.json()["id"]))
            login = client.post("/auth/login", json=credentials)
            assert login.status_code == 200, login.text
            return client

        try:
            yield create_authenticated_client
        finally:
            with Session(integration_database_engine) as database_session:
                with database_session.begin():
                    documents = database_session.scalars(
                        select(Document).where(Document.owner_id.in_(user_ids))
                    ).all()
                    for document in documents:
                        integration_s3_client.delete_object(
                            Bucket=integration_settings.s3_bucket,
                            Key=document.storage_key,
                        )
                        database_session.delete(document)
                    database_session.flush()
                    database_session.execute(delete(User).where(User.id.in_(user_ids)))


@pytest.fixture
def authenticated_client(authenticated_client_factory: Callable[[], TestClient]) -> TestClient:
    return authenticated_client_factory()


@pytest.fixture
def other_authenticated_client(
    authenticated_client_factory: Callable[[], TestClient],
) -> TestClient:
    return authenticated_client_factory()


@pytest.fixture
def pdf_content() -> bytes:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        return file.getvalue()
