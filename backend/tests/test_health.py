import pytest
from fastapi.testclient import TestClient

from documind.main import app

pytestmark = pytest.mark.usefixtures("s3_client_factory")


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
