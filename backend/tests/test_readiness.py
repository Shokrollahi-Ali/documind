from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.db.session import get_database_session
from documind.main import create_app


def test_readiness_when_database_available() -> None:
    database_session = AsyncMock(spec=AsyncSession)
    application = create_app()
    application.dependency_overrides[get_database_session] = lambda: database_session

    with TestClient(application) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_when_database_unavailable() -> None:
    database_session = AsyncMock(spec=AsyncSession)
    database_session.execute.side_effect = SQLAlchemyError("Database unavailable")

    application = create_app()
    application.dependency_overrides[get_database_session] = lambda: database_session

    with TestClient(application) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
