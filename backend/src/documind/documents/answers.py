from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from documind.documents.answer_generation import generate_answer
from documind.documents.answer_sources import resolve_answer_sources
from documind.documents.search import search_document
from documind.schemas.document_answer import DocumentAnswerResponse

INSUFFICIENT_CONTEXT_ANSWER = (
    "The retrieved passages do not contain enough information to answer this question."
)


async def answer_document(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: UUID,
    owner_id: UUID,
    question: str,
    embeddings: Embeddings,
    model: ChatOpenAI,
    *,
    limit: int,
) -> DocumentAnswerResponse:
    question = question.strip()

    if not question:
        raise ValueError("Question must not be empty")

    chunks = await search_document(
        session_factory=session_factory,
        document_id=document_id,
        owner_id=owner_id,
        query=question,
        embeddings=embeddings,
        limit=limit,
    )

    if not chunks:
        return DocumentAnswerResponse(
            answer=INSUFFICIENT_CONTEXT_ANSWER,
            sources=[],
        )

    generated_answer = await generate_answer(
        question=question,
        chunks=chunks,
        model=model,
    )

    if not generated_answer.has_supporting_context:
        return DocumentAnswerResponse(
            answer=INSUFFICIENT_CONTEXT_ANSWER,
            sources=[],
        )

    sources = resolve_answer_sources(
        cited_chunk_indexes=generated_answer.cited_chunk_indexes,
        chunks=chunks,
    )

    return DocumentAnswerResponse(
        answer=generated_answer.answer,
        sources=sources,
    )
