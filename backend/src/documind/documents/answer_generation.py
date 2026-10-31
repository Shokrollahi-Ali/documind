import re
from collections.abc import Sequence
from typing import Self

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import OpenAIRefusalError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from documind.documents.answer_prompt import (
    ANSWER_SYSTEM_PROMPT,
    format_answer_context,
)
from documind.documents.retrieval import RetrievedChunk


class AnswerGenerationError(Exception):
    pass


class AnswerRefusedError(Exception):
    pass


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    answer: str = Field(min_length=1)
    has_supporting_context: bool
    cited_chunk_indexes: list[int] = Field(
        description="Chunk indexes of the supplied passages supporting the answer",
    )

    @model_validator(mode="after")
    def validate_supporting_sources(self) -> Self:
        if self.has_supporting_context and not self.cited_chunk_indexes:
            raise ValueError("A supported answer must cite at least one chunk")

        if not self.has_supporting_context and self.cited_chunk_indexes:
            raise ValueError("An unsupported answer must not cite chunks")

        if any(index < 0 for index in self.cited_chunk_indexes):
            raise ValueError("Cited chunk indexes must not be negative")

        if len(self.cited_chunk_indexes) != len(set(self.cited_chunk_indexes)):
            raise ValueError("Cited chunk indexes must be unique")

        return self

    @model_validator(mode="after")
    def validate_inline_citations(self) -> Self:
        inline_indexes = {int(index) for index in re.findall(r"\[chunk ([0-9]+)\]", self.answer)}

        if inline_indexes != set(self.cited_chunk_indexes):
            raise ValueError("Inline chunk references must match the cited chunk indexes")

        return self


async def generate_answer(
    question: str,
    chunks: Sequence[RetrievedChunk],
    model: ChatOpenAI,
) -> GeneratedAnswer:
    question = question.strip()

    if not question:
        raise ValueError("Question must not be empty")

    if not chunks:
        raise ValueError("At least one passage is required to generate an answer")

    structured_model = model.with_structured_output(
        GeneratedAnswer,
        method="json_schema",
        strict=True,
    )

    try:
        result = await structured_model.ainvoke(
            [
                SystemMessage(content=ANSWER_SYSTEM_PROMPT),
                HumanMessage(content=format_answer_context(question, chunks)),
            ]
        )
    except OpenAIRefusalError as error:
        raise AnswerRefusedError("The model declined to answer this question") from error
    except ValueError as error:
        raise AnswerGenerationError("The model returned an invalid answer") from error

    if not isinstance(result, GeneratedAnswer):
        raise AnswerGenerationError("Answer generation did not return the expected structure")

    return result
