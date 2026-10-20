import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from documind.auth.login import InvalidCredentialsError, LoginResult, login_user
from documind.auth.passwords import hash_password
from documind.auth.sessions import get_session_user
from documind.auth.tokens import hash_session_token
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.models.auth_session import AuthSession
from documind.models.user import User
from documind.schemas.auth import LoginRequest

pytestmark = pytest.mark.integration

TEST_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def registered_user(integration_database_engine: Engine) -> Iterator[User]:
    user = User(
        id=uuid4(),
        email=f"login-{uuid4()}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
    )
    user_id = user.id

    try:
        with Session(integration_database_engine, expire_on_commit=False) as database_session:
            database_session.add(user)
            database_session.commit()
        yield user
    finally:
        with Session(integration_database_engine) as cleanup_session:
            with cleanup_session.begin():
                cleanup_session.execute(delete(User).where(User.id == user_id))


def test_login_commits_usable_session_with_hashed_token(
    integration_settings: Settings,
    integration_database_engine: Engine,
    registered_user: User,
) -> None:
    async def run_login() -> LoginResult:
        engine = create_database_engine(integration_settings)
        session_factory = create_session_factory(engine)

        try:
            async with session_factory() as database_session:
                result = await login_user(
                    database_session=database_session,
                    credentials=LoginRequest(
                        email=registered_user.email.upper(), password=TEST_PASSWORD
                    ),
                    session_lifetime_seconds=3600,
                )

            async with session_factory() as verification_session:
                authenticated_user = await get_session_user(
                    verification_session, result.session_token
                )
                assert authenticated_user is not None
                assert authenticated_user.id == registered_user.id

            return result
        finally:
            await engine.dispose()

    before_login = datetime.now(UTC)
    result = asyncio.run(run_login())
    after_login = datetime.now(UTC)

    assert result.user.id == registered_user.id
    with Session(integration_database_engine) as database_session:
        auth_session = database_session.scalars(
            select(AuthSession).where(AuthSession.user_id == registered_user.id)
        ).one()
        assert auth_session.token_hash == hash_session_token(result.session_token)
        assert auth_session.token_hash != result.session_token
        assert before_login + timedelta(hours=1) <= auth_session.expires_at
        assert auth_session.expires_at <= after_login + timedelta(hours=1)


@pytest.mark.parametrize("unknown_email", [False, True], ids=["wrong-password", "unknown-email"])
def test_invalid_login_does_not_persist_session(
    integration_settings: Settings,
    integration_database_engine: Engine,
    registered_user: User,
    unknown_email: bool,
) -> None:
    credentials = LoginRequest(email=registered_user.email, password="incorrect-password")
    if unknown_email:
        credentials = LoginRequest(email=f"missing-{uuid4()}@example.com", password=TEST_PASSWORD)

    async def run_login() -> None:
        engine = create_database_engine(integration_settings)
        session_factory = create_session_factory(engine)

        try:
            async with session_factory() as database_session:
                with pytest.raises(InvalidCredentialsError, match="Invalid email or password"):
                    await login_user(database_session, credentials, 3600)
                assert not database_session.in_transaction()
        finally:
            await engine.dispose()

    asyncio.run(run_login())

    with Session(integration_database_engine) as database_session:
        sessions = database_session.scalars(
            select(AuthSession).where(AuthSession.user_id == registered_user.id)
        ).all()
        assert sessions == []


def test_login_endpoint_issues_cookie_for_committed_session(
    integration_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    registered_user: User,
) -> None:
    response = integration_client.post(
        "/auth/login",
        json={"email": registered_user.email.upper(), "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"id", "email", "created_at"}
    assert response.json()["id"] == str(registered_user.id)
    assert response.json()["email"] == registered_user.email
    token = response.cookies[integration_settings.session_cookie_name]
    assert token not in response.text

    current_user_response = integration_client.get("/auth/me")
    assert current_user_response.status_code == 200
    assert current_user_response.json() == response.json()
    assert current_user_response.headers["Cache-Control"] == "no-store"

    with Session(integration_database_engine) as database_session:
        auth_session = database_session.scalars(
            select(AuthSession).where(AuthSession.user_id == registered_user.id)
        ).one()
        assert auth_session.token_hash == hash_session_token(token)
        assert auth_session.token_hash != token


@pytest.mark.parametrize("unknown_email", [False, True], ids=["wrong-password", "unknown-email"])
def test_login_endpoint_rejects_invalid_credentials_without_session(
    integration_client: TestClient,
    integration_database_engine: Engine,
    registered_user: User,
    unknown_email: bool,
) -> None:
    email = registered_user.email
    password = "wrong-password"
    if unknown_email:
        email = f"missing-{uuid4()}@example.com"
        password = TEST_PASSWORD

    response = integration_client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert "set-cookie" not in response.headers

    with Session(integration_database_engine) as database_session:
        sessions = database_session.scalars(
            select(AuthSession).where(AuthSession.user_id == registered_user.id)
        ).all()
        assert sessions == []


@pytest.mark.parametrize(
    "session_state", ["missing", "unknown", "expired", "deleted-session", "deleted-user"]
)
def test_current_user_rejects_invalid_authentication(
    integration_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    registered_user: User,
    session_state: str,
) -> None:
    login_response = integration_client.post(
        "/auth/login", json={"email": registered_user.email, "password": TEST_PASSWORD}
    )
    assert login_response.status_code == 200

    if session_state == "missing":
        integration_client.cookies.clear()
    elif session_state == "unknown":
        integration_client.cookies.clear()
        integration_client.cookies.set(integration_settings.session_cookie_name, "unknown-token")
    else:
        with Session(integration_database_engine) as database_session:
            with database_session.begin():
                if session_state == "expired":
                    database_session.execute(
                        update(AuthSession)
                        .where(AuthSession.user_id == registered_user.id)
                        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                    )
                elif session_state == "deleted-session":
                    database_session.execute(
                        delete(AuthSession).where(AuthSession.user_id == registered_user.id)
                    )
                else:
                    database_session.execute(delete(User).where(User.id == registered_user.id))

    response = integration_client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_logout_revokes_only_current_session_and_prevents_token_reuse(
    integration_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    registered_user: User,
) -> None:
    credentials = {"email": registered_user.email, "password": TEST_PASSWORD}
    cookie_name = integration_settings.session_cookie_name
    first_login = integration_client.post("/auth/login", json=credentials)
    assert first_login.status_code == 200
    first_token = first_login.cookies[cookie_name]
    second_login = integration_client.post("/auth/login", json=credentials)
    assert second_login.status_code == 200
    second_token = second_login.cookies[cookie_name]
    assert first_token != second_token

    response = integration_client.post("/auth/logout")

    assert response.status_code == 204
    assert response.content == b""
    assert cookie_name not in integration_client.cookies
    with Session(integration_database_engine) as database_session:
        remaining_session = database_session.scalars(
            select(AuthSession).where(AuthSession.user_id == registered_user.id)
        ).one()
        assert remaining_session.token_hash == hash_session_token(first_token)

    assert integration_client.get("/auth/me").status_code == 401
    replay_response = integration_client.get(
        "/auth/me", headers={"Cookie": f"{cookie_name}={second_token}"}
    )
    assert replay_response.status_code == 401
    other_session_response = integration_client.get(
        "/auth/me", headers={"Cookie": f"{cookie_name}={first_token}"}
    )
    assert other_session_response.status_code == 200
    assert other_session_response.json()["id"] == str(registered_user.id)

    repeated_logout = integration_client.post(
        "/auth/logout", headers={"Cookie": f"{cookie_name}={second_token}"}
    )
    assert repeated_logout.status_code == 204


@pytest.mark.parametrize("expired", [False, True], ids=["unknown-session", "expired-session"])
def test_logout_succeeds_for_unusable_session(
    integration_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    registered_user: User,
    expired: bool,
) -> None:
    cookie_name = integration_settings.session_cookie_name
    token = "unknown-token"
    if expired:
        login_response = integration_client.post(
            "/auth/login", json={"email": registered_user.email, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200
        token = login_response.cookies[cookie_name]
        with Session(integration_database_engine) as database_session:
            with database_session.begin():
                database_session.execute(
                    update(AuthSession)
                    .where(AuthSession.user_id == registered_user.id)
                    .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                )

    response = integration_client.post("/auth/logout", headers={"Cookie": f"{cookie_name}={token}"})

    assert response.status_code == 204
    assert cookie_name not in integration_client.cookies
    with Session(integration_database_engine) as database_session:
        sessions = database_session.scalars(
            select(AuthSession).where(AuthSession.user_id == registered_user.id)
        ).all()
        assert sessions == []
