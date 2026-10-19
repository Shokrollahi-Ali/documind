from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from documind.auth.passwords import hash_password
from documind.models.user import User
from documind.schemas.auth import RegisterRequest


class EmailAlreadyRegisteredError(Exception):
    pass


async def register_user(
    database_session: AsyncSession,
    registration: RegisterRequest,
) -> User:
    password_hash = await run_in_threadpool(
        hash_password,
        registration.password.get_secret_value(),
    )

    user = User(
        email=registration.email.lower(),
        password_hash=password_hash,
    )

    try:
        async with database_session.begin():
            database_session.add(user)
            await database_session.flush()
    except IntegrityError as error:
        if (
            isinstance(error.orig, UniqueViolation)
            and error.orig.diag.constraint_name == "uq_users_email"
        ):
            raise EmailAlreadyRegisteredError(
                "An account with this email already exists"
            ) from error
        raise

    return user
