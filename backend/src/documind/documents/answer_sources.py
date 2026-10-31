from collections.abc import Sequence

from documind.documents.retrieval import RetrievedChunk
from documind.schemas.document_answer import DocumentAnswerSource


class InvalidAnswerCitationError(ValueError):
    pass


def resolve_answer_sources(
    cited_chunk_indexes: Sequence[int],
    chunks: Sequence[RetrievedChunk],
) -> list[DocumentAnswerSource]:
    chunks_by_index = {chunk.chunk_index: chunk for chunk in chunks}
    sources = []

    for chunk_index in cited_chunk_indexes:
        chunk = chunks_by_index.get(chunk_index)

        if chunk is None:
            raise InvalidAnswerCitationError(
                f"Answer cites a chunk that was not supplied: {chunk_index}"
            )

        sources.append(
            DocumentAnswerSource(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
            )
        )

    return sources
