import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from documind.documents.answer_generation import AnswerGenerationError, GeneratedAnswer
from documind.documents.answer_sources import InvalidAnswerCitationError
from documind.documents.answers import INSUFFICIENT_CONTEXT_ANSWER, answer_document
from documind.documents.retrieval import RetrievedChunk
from documind.documents.search import DocumentNotFoundError, DocumentNotReadyError


def test_answers_with_original_source_metadata_and_scope() -> None:
    document_id, owner_id = uuid4(), uuid4()
    factory, embeddings, model = MagicMock(), MagicMock(), MagicMock()
    chunks = [
        RetrievedChunk(document_id, 7, 4, "First passage", 0.1),
        RetrievedChunk(document_id, 2, 1, "Second passage", 0.2),
    ]
    generated = GeneratedAnswer(
        answer="Second [chunk 2], first [chunk 7].",
        has_supporting_context=True,
        cited_chunk_indexes=[2, 7],
    )
    with (
        patch("documind.documents.answers.search_document", return_value=chunks) as search,
        patch("documind.documents.answers.generate_answer", return_value=generated) as generate,
    ):
        response = asyncio.run(
            answer_document(
                factory, document_id, owner_id, " Question ", embeddings, model, limit=3
            )
        )
    search.assert_awaited_once_with(
        session_factory=factory,
        document_id=document_id,
        owner_id=owner_id,
        query="Question",
        embeddings=embeddings,
        limit=3,
    )
    generate.assert_awaited_once_with(question="Question", chunks=chunks, model=model)
    assert response.answer == generated.answer
    assert [source.chunk_index for source in response.sources] == [2, 7]
    assert [source.page_number for source in response.sources] == [1, 4]
    assert [source.text for source in response.sources] == ["Second passage", "First passage"]
    assert all(source.document_id == document_id for source in response.sources)


@pytest.mark.parametrize("empty_retrieval", [True, False])
def test_insufficient_evidence_returns_fixed_answer(empty_retrieval: bool) -> None:
    chunks = [] if empty_retrieval else [RetrievedChunk(uuid4(), 0, 1, "Unrelated text", 0.1)]
    generated = GeneratedAnswer(
        answer="This model text must not be returned.",
        has_supporting_context=False,
        cited_chunk_indexes=[],
    )
    with (
        patch("documind.documents.answers.search_document", return_value=chunks),
        patch("documind.documents.answers.generate_answer", return_value=generated) as generate,
    ):
        response = asyncio.run(
            answer_document(
                MagicMock(), uuid4(), uuid4(), "Question", MagicMock(), MagicMock(), limit=3
            )
        )
    assert response.model_dump() == {"answer": INSUFFICIENT_CONTEXT_ANSWER, "sources": []}
    if empty_retrieval:
        generate.assert_not_awaited()
    else:
        generate.assert_awaited_once()


@pytest.mark.parametrize("error", [DocumentNotFoundError(), DocumentNotReadyError()])
def test_search_failure_prevents_generation(error: Exception) -> None:
    with (
        patch("documind.documents.answers.search_document", side_effect=error),
        patch("documind.documents.answers.generate_answer") as generate,
    ):
        with pytest.raises(type(error)):
            asyncio.run(
                answer_document(
                    MagicMock(), uuid4(), uuid4(), "Question", MagicMock(), MagicMock(), limit=3
                )
            )
    generate.assert_not_awaited()


def test_blank_question_does_not_search() -> None:
    with patch("documind.documents.answers.search_document") as search:
        with pytest.raises(ValueError, match="Question must not be empty"):
            asyncio.run(
                answer_document(
                    MagicMock(), uuid4(), uuid4(), "  ", MagicMock(), MagicMock(), limit=3
                )
            )
    search.assert_not_awaited()


def test_unknown_citation_is_not_returned_to_client() -> None:
    chunks = [RetrievedChunk(uuid4(), 7, 4, "Stored passage", 0.1)]
    generated = GeneratedAnswer(
        answer="Invented source [chunk 99].",
        has_supporting_context=True,
        cited_chunk_indexes=[99],
    )
    with (
        patch("documind.documents.answers.search_document", return_value=chunks),
        patch("documind.documents.answers.generate_answer", return_value=generated),
    ):
        with pytest.raises(InvalidAnswerCitationError):
            asyncio.run(
                answer_document(
                    MagicMock(), uuid4(), uuid4(), "Question", MagicMock(), MagicMock(), limit=3
                )
            )


def test_invalid_generation_is_not_replaced_with_insufficient_evidence() -> None:
    chunks = [RetrievedChunk(uuid4(), 7, 4, "Stored passage", 0.1)]
    with (
        patch("documind.documents.answers.search_document", return_value=chunks),
        patch("documind.documents.answers.generate_answer", side_effect=AnswerGenerationError()),
    ):
        with pytest.raises(AnswerGenerationError):
            asyncio.run(
                answer_document(
                    MagicMock(), uuid4(), uuid4(), "Question", MagicMock(), MagicMock(), limit=3
                )
            )
