from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from documind.models.user import User


@pytest.fixture
def current_user() -> User:
    return User(
        id=uuid4(),
        email="alice@example.com",
        password_hash="unused-in-document-api-tests",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def s3_client_factory() -> Iterator[MagicMock]:
    with patch("documind.main.create_s3_client") as client_factory:
        client_factory.return_value = MagicMock(spec_set=["close"])
        yield client_factory


def create_pdf(page_contents: list[bytes]) -> bytes:
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )

    with BytesIO() as file:
        with PdfWriter() as writer:
            for content in page_contents:
                page = writer.add_blank_page(width=612, height=792)
                page[NameObject("/Resources")] = DictionaryObject(
                    {
                        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
                    }
                )
                stream = DecodedStreamObject()
                stream.set_data(content)
                page[NameObject("/Contents")] = stream

            writer.write(file)

        return file.getvalue()


@pytest.fixture
def pdf_factory() -> Callable[[list[bytes]], bytes]:
    return create_pdf
