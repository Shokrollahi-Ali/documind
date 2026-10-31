import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from openai import APIError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.api.dependencies import (
    get_answer_model,
    get_current_user,
    get_embeddings,
    get_settings,
)
from documind.api.routes import DOCUMENT_ANSWER
from documind.core.config import Settings
from documind.db.session import get_database_session_factory
from documind.documents.answer_generation import (
    AnswerGenerationError,
    AnswerRefusedError,
)
from documind.documents.answer_sources import InvalidAnswerCitationError
from documind.documents.answers import answer_document
from documind.documents.search import DocumentNotFoundError, DocumentNotReadyError
from documind.models.user import User
from documind.schemas.document_answer import (
    DocumentAnswerRequest,
    DocumentAnswerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.post(DOCUMENT_ANSWER, response_model=DocumentAnswerResponse)
async def answer_document_question(
    document_id: UUID,
    answer_request: DocumentAnswerRequest,
    user: Annotated[User, Depends(get_current_user)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_database_session_factory),
    ],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
    model: Annotated[ChatOpenAI, Depends(get_answer_model)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentAnswerResponse:
    try:
        return await answer_document(
            session_factory=session_factory,
            document_id=document_id,
            owner_id=user.id,
            question=answer_request.question,
            embeddings=embeddings,
            model=model,
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
            detail="Document is not ready for questions",
        ) from error
    except AnswerRefusedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The model declined to answer this question",
        ) from error
    except (AnswerGenerationError, InvalidAnswerCitationError) as error:
        logger.error("Invalid generated answer: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A valid answer could not be generated",
        ) from error
    except APIError as error:
        logger.error("Answer provider failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document answer generation is temporarily unavailable",
        ) from error
    except SQLAlchemyError as error:
        logger.error("Answer database failure: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document answer generation is temporarily unavailable",
        ) from error
