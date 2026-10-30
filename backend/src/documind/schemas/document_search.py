from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentSearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    query: str = Field(min_length=1, max_length=2000)


class DocumentSearchMatch(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    chunk_index: int
    page_number: int
    text: str
    cosine_distance: float


class DocumentSearchResponse(BaseModel):
    matches: list[DocumentSearchMatch]
