import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.api.routes import REGISTER
from documind.auth.registration import EmailAlreadyRegisteredError, register_user
from documind.db.session import get_database_session
from documind.schemas.auth import RegisterRequest, UserResponse

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
