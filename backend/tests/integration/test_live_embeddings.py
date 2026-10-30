import asyncio
import os
from collections.abc import Callable
from math import isfinite
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.documents.tasks import run_document_processing
from documind.models.document import Document, DocumentStatus
from documind.models.document_chunk import DocumentChunk

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("DOCUMIND_RUN_LIVE_TESTS") != "1",
        reason="Set DOCUMIND_RUN_LIVE_TESTS=1 to allow billable OpenAI requests",
    ),
]


def test_uploaded_pdf_gets_live_embeddings(
    integration_settings: Settings,
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    pdf_factory: Callable[[list[bytes]], bytes],
) -> None:
    api_key = Settings().openai_api_key
    assert api_key is not None and api_key.get_secret_value().strip(), "OpenAI key is required"
    settings = integration_settings.model_copy(update={"openai_api_key": api_key})
    pdf = pdf_factory([b"BT /F1 12 Tf 72 720 Td (Documind finds information in documents.) Tj ET"])
    user = authenticated_client.get("/auth/me")
    assert user.status_code == 200
    owner_id = UUID(user.json()["id"])
    upload = authenticated_client.post(
        "/documents", files={"file": ("live-embedding-test.pdf", pdf, "application/pdf")}
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])

    assert asyncio.run(run_document_processing(settings, document_id, owner_id))

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.READY
        chunks = session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).all()
        assert len(chunks) == 1
        vector = chunks[0].embedding
        assert vector is not None
        assert len(vector) == 1536
        assert all(isfinite(value) for value in vector)
        assert any(value != 0 for value in vector)

    response = authenticated_client.get(f"/documents/{document_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
