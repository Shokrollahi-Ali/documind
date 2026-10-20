import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.api.dependencies import get_current_user, get_settings
from documind.api.routes import CURRENT_USER, LOGIN, REGISTER
from documind.auth.login import InvalidCredentialsError, login_user
from documind.auth.registration import EmailAlreadyRegisteredError, register_user
from documind.core.config import Settings
from documind.db.session import get_database_session
from documind.models.user import User
from documind.schemas.auth import LoginRequest, RegisterRequest, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post(
    REGISTER,
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    registration: RegisterRequest,
    database_session: Annotated[AsyncSession, Depends(get_database_session)],
) -> UserResponse:
    try:
        user = await register_user(
            database_session=database_session,
            registration=registration,
        )
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from error
    except SQLAlchemyError as error:
        logger.error("Registration database failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Registration is temporarily unavailable",
        ) from error

    return UserResponse.model_validate(user)


@router.post(LOGIN, response_model=UserResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
    database_session: Annotated[AsyncSession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    try:
        result = await login_user(
            database_session=database_session,
            credentials=credentials,
            session_lifetime_seconds=settings.session_lifetime_seconds,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from error
    except SQLAlchemyError as error:
        logger.error("Login database failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login is temporarily unavailable",
        ) from error

    user_response = UserResponse.model_validate(result.user)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        max_age=settings.session_lifetime_seconds,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"

    return user_response


@router.get(CURRENT_USER, response_model=UserResponse)
async def current_user(
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return UserResponse.model_validate(user)
