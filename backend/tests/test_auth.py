from collections.abc import Iterator
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from typing import Literal, cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.api.dependencies import get_settings
from documind.auth.login import InvalidCredentialsError, LoginResult
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


@pytest.mark.parametrize("environment", ["development", "test", "production"])
def test_login_returns_public_user_and_configured_cookie(
    client: TestClient, environment: Literal["development", "test", "production"]
) -> None:
    settings = Settings(
        _env_file=None,
        environment=environment,
        database_url="postgresql+psycopg://app:test-password@db.internal/documind",
        session_cookie_name="custom_session",
        session_lifetime_seconds=1800,
    )
    application = cast(FastAPI, client.app)
    application.dependency_overrides[get_settings] = lambda: settings
    user = User(
        id=uuid4(),
        email="alice@example.com",
        password_hash="private-password-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    result = LoginResult(user=user, session_token="private-session-token")

    with patch("documind.api.auth.login_user", return_value=result) as login_user:
        response = client.post(
            "/auth/login",
            json={"email": "Alice@example.com", "password": "correct-horse-battery-staple"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "created_at": "2026-01-01T00:00:00Z",
    }
    assert response.headers["Cache-Control"] == "no-store"
    cookies = SimpleCookie()
    cookies.load(response.headers["Set-Cookie"])
    cookie = cookies[settings.session_cookie_name]
    assert cookie.value == result.session_token
    assert cookie["httponly"]
    assert bool(cookie["secure"]) == (environment == "production")
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == "1800"
    assert cookie["domain"] == ""
    login_user.assert_awaited_once()
    arguments = login_user.call_args.kwargs
    assert arguments["session_lifetime_seconds"] == 1800
    assert arguments["credentials"].email == "Alice@example.com"
    assert arguments["credentials"].password.get_secret_value() == "correct-horse-battery-staple"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (InvalidCredentialsError("private-detail"), 401, "Invalid email or password"),
        (SQLAlchemyError("private-detail"), 503, "Login is temporarily unavailable"),
    ],
    ids=["invalid-credentials", "database-failure"],
)
def test_failed_login_does_not_issue_cookie_or_expose_details(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    with patch("documind.api.auth.login_user", side_effect=error):
        response = client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "correct-horse-battery-staple"},
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "set-cookie" not in response.headers
    assert "private-detail" not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "alice@example.com"},
        {"password": "password"},
        {"email": "invalid", "password": "password"},
        {"email": "alice@example.com", "password": ""},
        {"email": "alice@example.com", "password": "a" * 129},
        {"email": "alice@example.com", "password": None},
        {"email": "alice@example.com", "password": "password", "role": "admin"},
    ],
)
def test_invalid_login_request_does_not_call_service(
    client: TestClient, payload: dict[str, object]
) -> None:
    with patch("documind.api.auth.login_user") as login_user:
        response = client.post("/auth/login", json=payload)

    assert response.status_code == 422
    assert "set-cookie" not in response.headers
    login_user.assert_not_awaited()


def test_current_user_reads_configured_cookie_and_returns_public_fields(client: TestClient) -> None:
    settings = Settings(_env_file=None, environment="test", session_cookie_name="custom_session")
    application = cast(FastAPI, client.app)
    application.dependency_overrides[get_settings] = lambda: settings
    user = User(
        id=uuid4(),
        email="alice@example.com",
        password_hash="private-password-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with patch("documind.api.dependencies.get_session_user", return_value=user) as lookup:
        response = client.get("/auth/me", headers={"Cookie": "custom_session=private-token"})

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "created_at": "2026-01-01T00:00:00Z",
    }
    assert response.headers["Cache-Control"] == "no-store"
    lookup.assert_awaited_once()
    assert lookup.call_args.kwargs["session_token"] == "private-token"
    database_session = lookup.call_args.kwargs["database_session"]
    database_session.begin.return_value.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.parametrize("cookie_header", ["", "documind_session=", "unrelated=value"])
def test_current_user_rejects_missing_cookie_without_lookup(
    client: TestClient, cookie_header: str
) -> None:
    with patch("documind.api.dependencies.get_session_user") as lookup:
        response = client.get("/auth/me", headers={"Cookie": cookie_header})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    lookup.assert_not_awaited()


def test_current_user_rejects_invalid_session(client: TestClient) -> None:
    settings = cast(FastAPI, client.app).state.settings
    with patch("documind.api.dependencies.get_session_user", return_value=None):
        response = client.get(
            "/auth/me", headers={"Cookie": f"{settings.session_cookie_name}=invalid-token"}
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_current_user_database_failure_returns_unavailable(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    settings = cast(FastAPI, client.app).state.settings
    with patch(
        "documind.api.dependencies.get_session_user",
        side_effect=SQLAlchemyError("private-database-details"),
    ):
        response = client.get(
            "/auth/me", headers={"Cookie": f"{settings.session_cookie_name}=private-token"}
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is temporarily unavailable"}
    assert "Authentication database failure" in caplog.text
    assert "private-database-details" not in caplog.text
    assert "private-token" not in caplog.text
