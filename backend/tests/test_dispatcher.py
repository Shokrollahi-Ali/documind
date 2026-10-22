import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from celery import Celery
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from documind.core.config import Settings
from documind.dispatcher import run_dispatcher
from documind.documents.dispatch import dispatch_processing_requests


@pytest.mark.parametrize("first_result", [False, ConnectionError("Redis unavailable")])
def test_loop_waits_then_retries_with_a_fresh_session(
    first_result: bool | Exception,
) -> None:
    first_session = MagicMock(spec=AsyncSession)
    second_session = MagicMock(spec=AsyncSession)
    first_session.__aenter__.return_value = first_session
    second_session.__aenter__.return_value = second_session
    session_factory = Mock(side_effect=[first_session, second_session])
    celery_app = Mock(spec=Celery)

    with (
        patch(
            "documind.documents.dispatch.dispatch_next_processing_request",
            new_callable=AsyncMock,
            side_effect=[first_result, asyncio.CancelledError()],
        ) as dispatch,
        patch("documind.documents.dispatch.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(dispatch_processing_requests(session_factory, celery_app, 2.5))

    sleep.assert_awaited_once_with(2.5)
    assert dispatch.await_count == 2
    assert dispatch.await_args_list[0].kwargs["database_session"] is first_session
    assert dispatch.await_args_list[1].kwargs["database_session"] is second_session
    first_session.__aexit__.assert_awaited_once()
    second_session.__aexit__.assert_awaited_once()


def test_loop_processes_available_work_without_sleeping() -> None:
    session = MagicMock(spec=AsyncSession)
    session_factory = Mock(return_value=session)
    with (
        patch(
            "documind.documents.dispatch.dispatch_next_processing_request",
            new_callable=AsyncMock,
            side_effect=[True, True, asyncio.CancelledError()],
        ) as dispatch,
        patch("documind.documents.dispatch.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(dispatch_processing_requests(session_factory, Mock(spec=Celery), 5))

    assert dispatch.await_count == 3
    sleep.assert_not_awaited()


@pytest.mark.parametrize("error", [RuntimeError("Dispatcher failed"), asyncio.CancelledError()])
def test_runner_closes_resources_when_stopped(error: BaseException) -> None:
    settings = Settings(_env_file=None, processing_dispatch_interval_seconds=2.5)
    engine = MagicMock(spec=AsyncEngine)
    celery_app = Mock(spec=Celery)
    with (
        patch("documind.dispatcher.create_database_engine", return_value=engine),
        patch("documind.dispatcher.create_session_factory") as create_session_factory,
        patch("documind.dispatcher.create_celery_app", return_value=celery_app),
        patch(
            "documind.dispatcher.dispatch_processing_requests",
            new_callable=AsyncMock,
            side_effect=error,
        ) as dispatch,
    ):
        with pytest.raises(type(error)) as exception_info:
            asyncio.run(run_dispatcher(settings))

    assert exception_info.value is error
    dispatch.assert_awaited_once_with(
        session_factory=create_session_factory.return_value,
        celery_app=celery_app,
        interval_seconds=2.5,
    )
    celery_app.close.assert_called_once_with()
    engine.dispose.assert_awaited_once_with()


def test_runner_disposes_engine_when_celery_configuration_fails() -> None:
    engine = MagicMock(spec=AsyncEngine)
    with (
        patch("documind.dispatcher.create_database_engine", return_value=engine),
        patch("documind.dispatcher.create_session_factory"),
        patch("documind.dispatcher.create_celery_app", side_effect=ValueError("Invalid broker")),
    ):
        with pytest.raises(ValueError, match="Invalid broker"):
            asyncio.run(run_dispatcher(Settings(_env_file=None)))
    engine.dispose.assert_awaited_once_with()
