import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from documind.api.routes import READY
from documind.db.session import get_database_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(READY)
async def get_readiness(
    database_session: Annotated[AsyncSession, Depends(get_database_session)],
) -> dict[str, str]:
    try:
        await database_session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database connection check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from None
    return {"status": "ready"}
