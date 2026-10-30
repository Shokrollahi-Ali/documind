import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.retrieval import retrieve_document_chunks


@pytest.mark.parametrize(
    ("vector", "limit", "message"),
    [
        ([1.0] * 1536, 0, "Retrieval limit must be positive"),
        ([1.0] * 1536, -1, "Retrieval limit must be positive"),
        ([0.0] * 1536, 1, "Query embedding must not be a zero vector"),
        ([1.0], 1, "Each embedding must have 1536 dimensions"),
        ([float("nan")] * 1536, 1, "Embedding values must be finite"),
        ([float("inf")] * 1536, 1, "Embedding values must be finite"),
    ],
)
def test_rejects_invalid_search_before_database_access(
    vector: list[float], limit: int, message: str
) -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match=message):
        asyncio.run(retrieve_document_chunks(session, uuid4(), uuid4(), vector, limit=limit))

    session.execute.assert_not_awaited()
