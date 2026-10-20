import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.auth.login import InvalidCredentialsError, login_user
from documind.auth.passwords import DUMMY_PASSWORD_HASH
from documind.models.user import User
from documind.schemas.auth import LoginRequest


@pytest.fixture
def user() -> User:
    return User(id=uuid4(), email="alice@example.com", password_hash="stored-password-hash")


@pytest.fixture
def database_session(user: User) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    users = MagicMock()
    users.one_or_none.return_value = user
    session.scalars.return_value = users
    return session


@pytest.fixture
def credentials() -> LoginRequest:
    return LoginRequest(email="Alice@example.com", password="correct-horse-battery-staple")


def test_valid_credentials_create_session(
    database_session: MagicMock, user: User, credentials: LoginRequest
) -> None:
    with (
        patch("documind.auth.login.verify_password", return_value=True) as verify_password,
        patch(
            "documind.auth.login.create_auth_session", return_value="private-session-token"
        ) as create_session,
    ):
        result = asyncio.run(login_user(database_session, credentials, 3600))

    verify_password.assert_called_once_with(
        credentials.password.get_secret_value(), user.password_hash
    )
    create_session.assert_awaited_once_with(
        database_session=database_session, user_id=user.id, lifetime_seconds=3600
    )
    assert result.user is user
    assert result.session_token == "private-session-token"
    assert "private-session-token" not in repr(result)


@pytest.mark.parametrize(
    ("user_exists", "password_matches"),
    [(True, False), (False, False), (False, True)],
    ids=["wrong-password", "unknown-email", "unknown-email-even-if-dummy-matches"],
)
def test_invalid_credentials_never_create_session(
    database_session: MagicMock,
    user: User,
    credentials: LoginRequest,
    user_exists: bool,
    password_matches: bool,
) -> None:
    if not user_exists:
        database_session.scalars.return_value.one_or_none.return_value = None

    with (
        patch(
            "documind.auth.login.verify_password", return_value=password_matches
        ) as verify_password,
        patch("documind.auth.login.create_auth_session") as create_session,
    ):
        with pytest.raises(InvalidCredentialsError, match="Invalid email or password"):
            asyncio.run(login_user(database_session, credentials, 3600))

    expected_hash = user.password_hash if user_exists else DUMMY_PASSWORD_HASH
    verify_password.assert_called_once_with(credentials.password.get_secret_value(), expected_hash)
    create_session.assert_not_awaited()


@pytest.mark.parametrize("failure_stage", ["session-insert", "commit"])
def test_login_propagates_session_persistence_failure(
    database_session: MagicMock, credentials: LoginRequest, failure_stage: str
) -> None:
    database_error = SQLAlchemyError("Session persistence failed")

    with (
        patch("documind.auth.login.verify_password", return_value=True),
        patch(
            "documind.auth.login.create_auth_session", return_value="private-session-token"
        ) as create_session,
    ):
        if failure_stage == "session-insert":
            create_session.side_effect = database_error
        else:
            database_session.begin.return_value.__aexit__.side_effect = database_error

        with pytest.raises(SQLAlchemyError) as exception_info:
            asyncio.run(login_user(database_session, credentials, 3600))

    assert exception_info.value is database_error
