from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from documind.auth.tokens import generate_session_token, hash_session_token
from documind.models.auth_session import AuthSession
from documind.models.user import User


async def create_auth_session(
    database_session: AsyncSession,
    user_id: UUID,
    lifetime_seconds: int,
) -> str:
    session_token = generate_session_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=lifetime_seconds)

    auth_session = AuthSession(
        user_id=user_id,
        token_hash=hash_session_token(session_token),
        expires_at=expires_at,
    )

    database_session.add(auth_session)
    await database_session.flush()

    return session_token


async def get_session_user(
    database_session: AsyncSession,
    session_token: str,
) -> User | None:
    token_hash = hash_session_token(session_token)
    current_time = datetime.now(UTC)

    statement = (
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.expires_at > current_time,
        )
    )

    users = await database_session.scalars(statement)
    return users.one_or_none()


async def delete_auth_session(
    database_session: AsyncSession,
    session_token: str,
) -> None:
    token_hash = hash_session_token(session_token)
    statement = delete(AuthSession).where(AuthSession.token_hash == token_hash)

    async with database_session.begin():
        await database_session.execute(statement)
