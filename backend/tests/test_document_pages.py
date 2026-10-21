import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from documind.documents.pages import replace_document_pages


def test_rejects_empty_pages_before_starting_transaction() -> None:
    database_session = MagicMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="At least one extracted page is required"):
        asyncio.run(
            replace_document_pages(
                database_session=database_session,
                document_id=uuid4(),
                owner_id=uuid4(),
                pages=[],
            )
        )

    database_session.begin.assert_not_called()
    database_session.execute.assert_not_awaited()
