from collections.abc import Iterator
from contextlib import closing
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from documind.core.config import Settings
from documind.main import create_app
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
def integration_s3_client(
    integration_settings: Settings,
) -> Iterator["S3Client"]:
    with closing(create_s3_client(integration_settings)) as client:
        yield client


@pytest.fixture
def pdf_content() -> bytes:
    with BytesIO() as file:
        with PdfWriter() as writer:
            writer.add_blank_page(width=612, height=792)
            writer.write(file)

        return file.getvalue()
