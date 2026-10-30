from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from documind.core.config import Settings
from documind.documents.tasks import process_document_task

REQUEST = MagicMock(spec=httpx.Request)


@pytest.fixture(autouse=True)
def failure_recorder() -> Iterator[AsyncMock]:
    with patch("documind.documents.tasks.record_embedding_failure") as recorder:
        yield recorder


@pytest.mark.parametrize(
    "error",
    [
        APIConnectionError(request=REQUEST),
        APITimeoutError(request=REQUEST),
        RateLimitError(
            "Rate limited",
            response=MagicMock(spec=httpx.Response, status_code=429, headers={}),
            body=None,
        ),
        InternalServerError(
            "Unavailable",
            response=MagicMock(spec=httpx.Response, status_code=503, headers={}),
            body=None,
        ),
    ],
)
def test_retries_temporary_failure_and_returns_success(
    error: Exception, failure_recorder: AsyncMock
) -> None:
    with (
        patch("documind.documents.tasks.Settings", return_value=Settings(_env_file=None)),
        patch(
            "documind.documents.tasks.run_document_processing",
            new_callable=AsyncMock,
            side_effect=[error, True],
        ) as process,
    ):
        result = process_document_task.apply(args=(str(uuid4()), str(uuid4())), throw=False)

    assert result.successful()
    assert result.result is True
    assert process.await_count == 2
    assert process.await_args_list[0] == process.await_args_list[1]
    failure_recorder.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError(
            "Invalid key",
            response=MagicMock(spec=httpx.Response, status_code=401, headers={}),
            body=None,
        ),
        BadRequestError(
            "Invalid input",
            response=MagicMock(spec=httpx.Response, status_code=400, headers={}),
            body=None,
        ),
        ValueError("Embedding count must match chunk count"),
    ],
)
def test_does_not_retry_permanent_failure(error: Exception, failure_recorder: AsyncMock) -> None:
    with (
        patch("documind.documents.tasks.Settings", return_value=Settings(_env_file=None)),
        patch(
            "documind.documents.tasks.run_document_processing",
            new_callable=AsyncMock,
            side_effect=error,
        ) as process,
    ):
        result = process_document_task.apply(args=(str(uuid4()), str(uuid4())), throw=False)

    assert result.failed()
    assert str(result.result) == str(error)
    process.assert_awaited_once()
    failure_recorder.assert_awaited_once()


def test_stops_after_three_retries(failure_recorder: AsyncMock) -> None:
    with (
        patch("documind.documents.tasks.Settings", return_value=Settings(_env_file=None)),
        patch(
            "documind.documents.tasks.run_document_processing",
            new_callable=AsyncMock,
            side_effect=APIConnectionError(request=REQUEST),
        ) as process,
    ):
        result = process_document_task.apply(args=(str(uuid4()), str(uuid4())), throw=False)

    assert result.failed()
    assert str(result.result) == "Connection error."
    assert process.await_count == 4
    failure_recorder.assert_awaited_once()


@pytest.mark.parametrize("argument_style", ["positional", "keyword", "mixed"])
def test_failure_callback_records_correct_document(
    argument_style: str, failure_recorder: AsyncMock
) -> None:
    document_id, owner_id = uuid4(), uuid4()
    settings = Settings(_env_file=None)
    args: tuple[str, ...] = ()
    kwargs: dict[str, str] = {}
    if argument_style == "positional":
        args = (str(document_id), str(owner_id))
    elif argument_style == "keyword":
        kwargs = {"document_id": str(document_id), "owner_id": str(owner_id)}
    else:
        args = (str(document_id),)
        kwargs = {"owner_id": str(owner_id)}

    with (
        patch("documind.documents.tasks.Settings", return_value=settings),
        patch(
            "documind.documents.tasks.run_document_processing", side_effect=ValueError("Invalid")
        ),
    ):
        result = process_document_task.apply(args=args, kwargs=kwargs, throw=False)

    assert result.failed()
    failure_recorder.assert_awaited_once_with(
        settings=settings, document_id=document_id, owner_id=owner_id
    )


def test_recording_error_preserves_original_failure(
    failure_recorder: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    failure_recorder.side_effect = RuntimeError("Database unavailable")
    with (
        patch("documind.documents.tasks.Settings", return_value=Settings(_env_file=None)),
        patch(
            "documind.documents.tasks.run_document_processing",
            side_effect=ValueError("Original failure"),
        ),
    ):
        result = process_document_task.apply(args=(str(uuid4()), str(uuid4())), throw=False)

    assert result.failed()
    assert str(result.result) == "Original failure"
    assert "Failed to record embedding failure" in caplog.text
