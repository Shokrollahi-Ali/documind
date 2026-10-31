from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentAnswerRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(min_length=1, max_length=2000)


class DocumentAnswerSource(BaseModel):
    document_id: UUID
    chunk_index: int = Field(ge=0)
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1)


class DocumentAnswerResponse(BaseModel):
    answer: str = Field(min_length=1)
    sources: list[DocumentAnswerSource]
