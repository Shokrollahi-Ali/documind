import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from celery import Celery

from documind.documents.queue import publish_document_processing


def test_publishes_document_processing_task() -> None:
    celery_app = Mock(spec=Celery)
    document_id = uuid4()
    owner_id = uuid4()

    with patch(
        "documind.documents.queue.run_in_threadpool",
        new_callable=AsyncMock,
    ) as run_in_threadpool:
        asyncio.run(
            publish_document_processing(
                celery_app=celery_app,
                document_id=document_id,
                owner_id=owner_id,
            )
        )

    run_in_threadpool.assert_awaited_once_with(
        celery_app.send_task,
        "documind.process_document",
        kwargs={
            "document_id": str(document_id),
            "owner_id": str(owner_id),
        },
    )


def test_propagates_publishing_failure() -> None:
    celery_app = Mock(spec=Celery)
    publishing_error = ConnectionError("Redis is unavailable")

    with patch(
        "documind.documents.queue.run_in_threadpool",
        new_callable=AsyncMock,
        side_effect=publishing_error,
    ):
        with pytest.raises(ConnectionError) as exception_info:
            asyncio.run(
                publish_document_processing(
                    celery_app=celery_app,
                    document_id=uuid4(),
                    owner_id=uuid4(),
                )
            )

    assert exception_info.value is publishing_error
