from uuid import UUID

from celery import Celery
from starlette.concurrency import run_in_threadpool


async def publish_document_processing(
    celery_app: Celery,
    document_id: UUID,
    owner_id: UUID,
) -> None:
    await run_in_threadpool(
        celery_app.send_task,
        "documind.process_document",
        kwargs={
            "document_id": str(document_id),
            "owner_id": str(owner_id),
        },
    )
