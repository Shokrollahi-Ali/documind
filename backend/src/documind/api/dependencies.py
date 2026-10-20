import logging
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.auth.sessions import get_session_user
from documind.core.config import Settings
from documind.db.session import get_database_session
from documind.models.user import User

logger = logging.getLogger(__name__)


async def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    database_session: Annotated[AsyncSession, Depends(get_database_session)],
) -> User:
    session_token = request.cookies.get(settings.session_cookie_name)

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        async with database_session.begin():
            user = await get_session_user(
                database_session=database_session,
                session_token=session_token,
            )
    except SQLAlchemyError as error:
        logger.error("Authentication database failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable",
        ) from error

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return user
