import asyncio
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.status import transition_document_status
from documind.models.document import Document, DocumentStatus

pytestmark = pytest.mark.integration


def test_status_transition_rejects_outdated_expected_status(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("status-test.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        owner_id = document.owner_id

    async def attempt_transitions() -> None:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)

            async with session_factory() as session:
                changed = await transition_document_status(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    expected_status=DocumentStatus.UPLOADED,
                    new_status=DocumentStatus.PROCESSING,
                )
                assert changed is True

            async with session_factory() as session:
                changed = await transition_document_status(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    expected_status=DocumentStatus.UPLOADED,
                    new_status=DocumentStatus.FAILED,
                )
                assert changed is False
        finally:
            await engine.dispose()

    asyncio.run(attempt_transitions())

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING
