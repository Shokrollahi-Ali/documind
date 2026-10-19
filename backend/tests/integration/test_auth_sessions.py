import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from documind.auth.sessions import create_auth_session, get_session_user
from documind.auth.tokens import generate_session_token, hash_session_token
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.models.auth_session import AuthSession
from documind.models.user import User

pytestmark = pytest.mark.integration


def test_valid_session_returns_its_user(integration_settings: Settings) -> None:
    async def run_test() -> None:
        engine = create_database_engine(integration_settings)
        session_factory = create_session_factory(engine)

        try:
            async with session_factory() as database_session:
                user = User(
                    email=f"{uuid4()}@example.com",
                    password_hash="unused-in-session-lookup-test",
                )
                database_session.add(user)
                await database_session.flush()

                session_token = await create_auth_session(
                    database_session=database_session,
                    user_id=user.id,
                    lifetime_seconds=3600,
                )

                found_user = await get_session_user(
                    database_session=database_session,
                    session_token=session_token,
                )

                assert found_user is not None
                assert found_user.id == user.id
        finally:
            await engine.dispose()

    asyncio.run(run_test())


@pytest.mark.parametrize("expired", [True, False], ids=["expired-session", "unknown-token"])
def test_invalid_session_returns_no_user(integration_settings: Settings, expired: bool) -> None:
    async def run_test() -> None:
        engine = create_database_engine(integration_settings)
        session_factory = create_session_factory(engine)

        try:
            async with session_factory() as database_session:
                user = User(
                    email=f"{uuid4()}@example.com",
                    password_hash="unused-in-session-lookup-test",
                )
                database_session.add(user)
                await database_session.flush()

                stored_token = generate_session_token()
                current_time = datetime.now(UTC)
                if expired:
                    expires_at = current_time - timedelta(hours=1)
                    lookup_token = stored_token
                else:
                    expires_at = current_time + timedelta(hours=1)
                    lookup_token = generate_session_token()

                database_session.add(
                    AuthSession(
                        user_id=user.id,
                        token_hash=hash_session_token(stored_token),
                        expires_at=expires_at,
                    )
                )
                await database_session.flush()

                found_user = await get_session_user(
                    database_session=database_session,
                    session_token=lookup_token,
                )

                assert found_user is None
        finally:
            await engine.dispose()

    asyncio.run(run_test())
