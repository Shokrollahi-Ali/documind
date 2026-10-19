import asyncio
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.auth.passwords import verify_password
from documind.auth.registration import register_user
from documind.schemas.auth import RegisterRequest


def test_registration_normalizes_email_and_hashes_password() -> None:
    database_session = MagicMock(spec=AsyncSession)
    password = "correct-horse-battery-staple"
    registration = RegisterRequest(
        email="Alice@example.com",
        password=password,
    )

    user = asyncio.run(
        register_user(
            database_session=database_session,
            registration=registration,
        )
    )

    assert user.email == "alice@example.com"
    assert user.password_hash != password
    assert verify_password(password, user.password_hash)

    database_session.add.assert_called_once_with(user)
    database_session.flush.assert_awaited_once_with()
    database_session.begin.assert_called_once_with()


def test_registration_propagates_database_failure() -> None:
    database_session = MagicMock(spec=AsyncSession)
    database_error = SQLAlchemyError("Database unavailable")
    database_session.flush.side_effect = database_error
    registration = RegisterRequest(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )

    with pytest.raises(SQLAlchemyError) as exception_info:
        asyncio.run(
            register_user(
                database_session=database_session,
                registration=registration,
            )
        )

    assert exception_info.value is database_error
