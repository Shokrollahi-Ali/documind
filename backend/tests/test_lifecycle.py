from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from documind.core.config import Settings
from documind.main import create_app


def test_creates_and_closes_application_resources(s3_client_factory: MagicMock) -> None:
    settings = Settings(environment="test")
    application = create_app(settings)
    s3_client = s3_client_factory.return_value
    engine = AsyncMock(spec=AsyncEngine)

    with patch("documind.main.create_database_engine", return_value=engine):
        with TestClient(application):
            assert application.state.session_factory is not None
            assert application.state.s3_client is s3_client
            s3_client_factory.assert_called_once_with(settings)
            s3_client.close.assert_not_called()
            engine.dispose.assert_not_awaited()

        s3_client.close.assert_called_once_with()
        engine.dispose.assert_awaited_once_with()


def test_disposes_database_engine_when_s3_startup_fails(s3_client_factory: MagicMock) -> None:
    settings = Settings(environment="test")
    application = create_app(settings)
    engine = AsyncMock(spec=AsyncEngine)
    s3_client_factory.side_effect = ValueError("Invalid S3 configuration")

    with patch("documind.main.create_database_engine", return_value=engine):
        with pytest.raises(ValueError, match="Invalid S3 configuration"):
            with TestClient(application):
                pytest.fail("Application startup should have failed")

        engine.dispose.assert_awaited_once_with()
