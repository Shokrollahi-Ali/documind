import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from documind.core.config import Settings
from documind.documents.extraction import PdfExtractionError
from documind.documents.tasks import (
    process_document_task,
    run_document_processing,
)


def test_processing_failure_closes_resources() -> None:
    settings = Settings(_env_file=None)
    engine = MagicMock(spec=AsyncEngine)
    s3_client = MagicMock(spec=["close"])
    error = PdfExtractionError("Could not extract text from the PDF")
    document_id = uuid4()
    owner_id = uuid4()

    with (
        patch(
            "documind.documents.tasks.create_database_engine",
            return_value=engine,
        ),
        patch("documind.documents.tasks.create_session_factory") as create_session_factory,
        patch(
            "documind.documents.tasks.create_s3_client",
            return_value=s3_client,
        ),
        patch(
            "documind.documents.tasks.extract_and_store_document_pages",
            new_callable=AsyncMock,
            side_effect=error,
        ) as process_document,
    ):
        with pytest.raises(PdfExtractionError) as exception_info:
            asyncio.run(
                run_document_processing(
                    settings=settings,
                    document_id=document_id,
                    owner_id=owner_id,
                )
            )

    assert exception_info.value is error
    process_document.assert_awaited_once_with(
        session_factory=create_session_factory.return_value,
        s3_client=s3_client,
        bucket=settings.s3_bucket,
        document_id=document_id,
        owner_id=owner_id,
        lease_seconds=settings.processing_lease_seconds,
    )
    s3_client.close.assert_called_once_with()
    engine.dispose.assert_awaited_once_with()


@pytest.mark.parametrize("extracted", [False, True])
def test_chunking_runs_only_after_successful_extraction(extracted: bool) -> None:
    settings = Settings(_env_file=None)
    engine = MagicMock(spec=AsyncEngine)
    s3_client = MagicMock(spec=["close"])
    document_id = uuid4()
    owner_id = uuid4()

    with (
        patch("documind.documents.tasks.create_database_engine", return_value=engine),
        patch("documind.documents.tasks.create_session_factory") as create_session_factory,
        patch("documind.documents.tasks.create_s3_client", return_value=s3_client),
        patch(
            "documind.documents.tasks.extract_and_store_document_pages",
            new_callable=AsyncMock,
            return_value=extracted,
        ),
        patch(
            "documind.documents.tasks.chunk_and_store_document",
            new_callable=AsyncMock,
            return_value=True,
        ) as chunk_document,
    ):
        result = asyncio.run(run_document_processing(settings, document_id, owner_id))

    assert result is extracted
    if extracted:
        chunk_document.assert_awaited_once_with(
            session_factory=create_session_factory.return_value,
            document_id=document_id,
            owner_id=owner_id,
            chunk_size=settings.chunk_size_chars,
            chunk_overlap=settings.chunk_overlap_chars,
        )
    else:
        chunk_document.assert_not_awaited()
    s3_client.close.assert_called_once_with()
    engine.dispose.assert_awaited_once_with()


@pytest.mark.parametrize("processing_result", [True, False])
def test_task_converts_ids_and_returns_processing_result(
    processing_result: bool,
) -> None:
    settings = Settings(_env_file=None)
    document_id = uuid4()
    owner_id = uuid4()

    with (
        patch(
            "documind.documents.tasks.Settings",
            return_value=settings,
        ),
        patch(
            "documind.documents.tasks.run_document_processing",
            new_callable=AsyncMock,
            return_value=processing_result,
        ) as process_document,
    ):
        result = process_document_task.run(
            str(document_id),
            str(owner_id),
        )

    assert result is processing_result
    process_document.assert_awaited_once_with(
        settings=settings,
        document_id=document_id,
        owner_id=owner_id,
    )
