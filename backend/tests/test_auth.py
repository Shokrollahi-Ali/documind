from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.auth.registration import EmailAlreadyRegisteredError
from documind.core.config import Settings
from documind.db.session import get_database_session
from documind.main import create_app
from documind.models.user import User


@pytest.fixture
def client(s3_client_factory: MagicMock) -> Iterator[TestClient]:
    application = create_app(Settings(environment="test"))
    database_session = MagicMock(spec=AsyncSession)
    application.dependency_overrides[get_database_session] = lambda: database_session

    with TestClient(application) as test_client:
        yield test_client


def test_registration_returns_public_user_information(client: TestClient) -> None:
    user_id = uuid4()
    user = User(
        id=user_id,
        email="alice@example.com",
        password_hash="private-password-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with patch(
        "documind.api.auth.register_user",
        return_value=user,
    ) as register_user:
        response = client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(user_id),
        "email": "alice@example.com",
        "created_at": "2026-01-01T00:00:00Z",
    }
    register_user.assert_awaited_once()
    registration = register_user.call_args.kwargs["registration"]
    assert registration.email == "alice@example.com"
    assert registration.password.get_secret_value() == "correct-horse-battery-staple"


def test_registration_returns_conflict_for_duplicate_email(client: TestClient) -> None:
    with patch(
        "documind.api.auth.register_user",
        side_effect=EmailAlreadyRegisteredError(),
    ):
        response = client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
            },
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "An account with this email already exists"}


def test_registration_returns_unavailable_without_exposing_database_details(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    private_detail = "private-password-hash-in-sql-parameters"
    with patch(
        "documind.api.auth.register_user",
        side_effect=SQLAlchemyError(private_detail),
    ):
        response = client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
            },
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Registration is temporarily unavailable"}
    assert "Registration database failure" in caplog.text
    assert private_detail not in caplog.text
    assert private_detail not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "alice@example.com"},
        {"password": "correct-horse-battery-staple"},
        {"email": "not-an-email", "password": "correct-horse-battery-staple"},
        {"email": "alice@example.com", "password": "a" * 14},
        {"email": "alice@example.com", "password": "a" * 129},
        {"email": "alice@example.com", "password": None},
        {
            "email": "alice@example.com",
            "password": "correct-horse-battery-staple",
            "role": "admin",
        },
    ],
    ids=[
        "empty-body",
        "missing-password",
        "missing-email",
        "invalid-email",
        "short-password",
        "long-password",
        "null-password",
        "unexpected-field",
    ],
)
def test_invalid_registration_does_not_call_service(
    client: TestClient, payload: dict[str, object]
) -> None:
    with patch("documind.api.auth.register_user") as register_user:
        response = client.post("/auth/register", json=payload)

    assert response.status_code == 422
    register_user.assert_not_awaited()


def test_malformed_registration_json_does_not_call_service(client: TestClient) -> None:
    with patch("documind.api.auth.register_user") as register_user:
        response = client.post(
            "/auth/register",
            content="{",
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 422
    register_user.assert_not_awaited()
