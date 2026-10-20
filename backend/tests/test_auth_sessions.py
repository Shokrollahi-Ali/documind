import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.auth.sessions import create_auth_session, delete_auth_session
from documind.auth.tokens import hash_session_token
from documind.models.auth_session import AuthSession


def test_creates_session_with_hashed_token_and_expiration() -> None:
    database_session = MagicMock(spec=AsyncSession)
    user_id = uuid4()
    lifetime_seconds = 3600
    before_creation = datetime.now(UTC)

    session_token = asyncio.run(
        create_auth_session(
            database_session=database_session,
            user_id=user_id,
            lifetime_seconds=lifetime_seconds,
        )
    )

    after_creation = datetime.now(UTC)
    database_session.add.assert_called_once()
    auth_session = database_session.add.call_args.args[0]

    assert isinstance(auth_session, AuthSession)
    assert auth_session.user_id == user_id
    assert auth_session.token_hash == hash_session_token(session_token)
    assert auth_session.token_hash != session_token

    lifetime = timedelta(seconds=lifetime_seconds)
    assert before_creation + lifetime <= auth_session.expires_at <= after_creation + lifetime

    database_session.flush.assert_awaited_once_with()
    database_session.commit.assert_not_awaited()


@pytest.mark.parametrize("failure_stage", ["delete", "commit"])
def test_session_deletion_propagates_database_failure(failure_stage: str) -> None:
    database_session = MagicMock(spec=AsyncSession)
    database_error = SQLAlchemyError("Session deletion failed")
    if failure_stage == "delete":
        database_session.execute.side_effect = database_error
    else:
        database_session.begin.return_value.__aexit__.side_effect = database_error

    with pytest.raises(SQLAlchemyError) as exception_info:
        asyncio.run(delete_auth_session(database_session, "private-session-token"))

    assert exception_info.value is database_error


def test_does_not_return_token_when_session_insert_fails() -> None:
    database_session = MagicMock(spec=AsyncSession)
    database_session.flush.side_effect = SQLAlchemyError("Session insert failed")

    with pytest.raises(SQLAlchemyError, match="Session insert failed"):
        asyncio.run(
            create_auth_session(
                database_session=database_session,
                user_id=uuid4(),
                lifetime_seconds=3600,
            )
        )

    database_session.commit.assert_not_awaited()
