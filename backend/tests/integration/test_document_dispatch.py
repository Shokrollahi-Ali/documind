import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from celery import Celery
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.dispatch import dispatch_next_processing_request
from documind.models.document import Document
from documind.models.document_processing_request import DocumentProcessingRequest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("publishing_fails", [False, True])
def test_dispatch_commits_only_after_successful_publishing(
    publishing_fails: bool,
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("dispatch.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        owner_id = document.owner_id
        request_id = session.scalars(
            select(DocumentProcessingRequest.id).where(
                DocumentProcessingRequest.document_id == document_id
            )
        ).one()

    celery_app = Mock(spec=Celery)
    publishing_error = ConnectionError("Redis is unavailable")

    async def attempt_dispatch() -> bool:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                return await dispatch_next_processing_request(session, celery_app)
        finally:
            await engine.dispose()

    with patch(
        "documind.documents.dispatch.publish_document_processing",
        new_callable=AsyncMock,
        side_effect=publishing_error if publishing_fails else None,
    ) as publish:
        if publishing_fails:
            with pytest.raises(ConnectionError) as exception_info:
                asyncio.run(attempt_dispatch())
            assert exception_info.value is publishing_error
        else:
            assert asyncio.run(attempt_dispatch()) is True
    publish.assert_awaited_once_with(
        celery_app=celery_app,
        document_id=document_id,
        owner_id=owner_id,
    )

    with Session(integration_database_engine) as session:
        remaining_request = session.get(DocumentProcessingRequest, request_id)
        if publishing_fails:
            assert remaining_request is not None
            assert remaining_request.document_id == document_id
        else:
            assert remaining_request is None
        assert session.get(Document, document_id) is not None


def test_concurrent_dispatchers_skip_locked_request(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    document_ids = []
    for filename in ["first.pdf", "second.pdf"]:
        response = authenticated_client.post(
            "/documents",
            files={"file": (filename, pdf_content, "application/pdf")},
        )
        assert response.status_code == 201, response.text
        document_ids.append(UUID(response.json()["id"]))

    celery_app = Mock(spec=Celery)

    async def dispatch_concurrently() -> None:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as first_session:
                async with first_session.begin():
                    locked_request = await first_session.scalar(
                        select(DocumentProcessingRequest)
                        .where(DocumentProcessingRequest.document_id == document_ids[0])
                        .with_for_update()
                    )
                    assert locked_request is not None
                    async with session_factory() as second_session:
                        assert (
                            await asyncio.wait_for(
                                dispatch_next_processing_request(second_session, celery_app),
                                timeout=5,
                            )
                            is True
                        )
                assert await dispatch_next_processing_request(first_session, celery_app) is True
                assert await dispatch_next_processing_request(first_session, celery_app) is False
        finally:
            await engine.dispose()

    with patch(
        "documind.documents.dispatch.publish_document_processing",
        new_callable=AsyncMock,
    ) as publish:
        asyncio.run(dispatch_concurrently())

    published_ids = [call.kwargs["document_id"] for call in publish.await_args_list]
    assert published_ids == [document_ids[1], document_ids[0]]
    with Session(integration_database_engine) as session:
        remaining = session.scalars(
            select(DocumentProcessingRequest).where(
                DocumentProcessingRequest.document_id.in_(document_ids)
            )
        ).all()
        assert remaining == []
