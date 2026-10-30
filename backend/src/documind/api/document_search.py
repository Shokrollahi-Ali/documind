import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.embeddings import Embeddings
from openai import APIError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.api.dependencies import get_current_user, get_embeddings, get_settings
from documind.api.routes import DOCUMENT_SEARCH
from documind.core.config import Settings
from documind.db.session import get_database_session_factory
from documind.documents.search import (
    DocumentNotFoundError,
    DocumentNotReadyError,
    search_document,
)
from documind.models.user import User
from documind.schemas.document_search import (
    DocumentSearchMatch,
    DocumentSearchRequest,
    DocumentSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.post(DOCUMENT_SEARCH, response_model=DocumentSearchResponse)
async def search_document_content(
    document_id: UUID,
    search_request: DocumentSearchRequest,
    user: Annotated[User, Depends(get_current_user)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_database_session_factory),
    ],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentSearchResponse:
    try:
        chunks = await search_document(
            session_factory=session_factory,
            document_id=document_id,
            owner_id=user.id,
            query=search_request.query,
            embeddings=embeddings,
            limit=settings.retrieval_top_k,
        )
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from error
    except DocumentNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is not ready for search",
        ) from error
    except APIError as error:
        logger.error("Search embedding provider failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document search is temporarily unavailable",
        ) from error
    except SQLAlchemyError as error:
        logger.error("Search database failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document search is temporarily unavailable",
        ) from error

    return DocumentSearchResponse(
        matches=[DocumentSearchMatch.model_validate(chunk) for chunk in chunks],
    )
