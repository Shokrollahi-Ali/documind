from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def s3_client_factory() -> Iterator[MagicMock]:
    with patch("documind.main.create_s3_client") as client_factory:
        client_factory.return_value = MagicMock(spec_set=["close"])
        yield client_factory
