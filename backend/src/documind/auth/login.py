from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from documind.auth.passwords import DUMMY_PASSWORD_HASH, verify_password
from documind.auth.sessions import create_auth_session
from documind.models.user import User
from documind.schemas.auth import LoginRequest


class InvalidCredentialsError(Exception):
    pass


@dataclass
class LoginResult:
    user: User
    session_token: str = field(repr=False)


async def login_user(
    database_session: AsyncSession,
    credentials: LoginRequest,
    session_lifetime_seconds: int,
) -> LoginResult:
    async with database_session.begin():
        statement = select(User).where(User.email == credentials.email.lower())
        users = await database_session.scalars(statement)
        user = users.one_or_none()

        password_hash = DUMMY_PASSWORD_HASH
        if user is not None:
            password_hash = user.password_hash

        password_matches = await run_in_threadpool(
            verify_password,
            credentials.password.get_secret_value(),
            password_hash,
        )

        if user is None or not password_matches:
            raise InvalidCredentialsError("Invalid email or password")

        session_token = await create_auth_session(
            database_session=database_session,
            user_id=user.id,
            lifetime_seconds=session_lifetime_seconds,
        )

    return LoginResult(user=user, session_token=session_token)
