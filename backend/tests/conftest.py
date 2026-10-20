from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

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
