import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, Request
from langchain_openai import ChatOpenAI
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from documind.api.dependencies import get_answer_model
from documind.core.config import Settings
from documind.documents.answer_model import create_answer_model
from documind.main import create_app


@pytest.mark.parametrize(
    ("model_name", "api_key"),
    [(None, "test-key"), ("   ", "test-key"), ("test-model", None), ("test-model", "   ")],
)
def test_factory_rejects_missing_configuration(model_name: str | None, api_key: str | None) -> None:
    settings = Settings(
        answer_model=model_name,
        openai_api_key=SecretStr(api_key) if api_key is not None else None,
    )
    with patch("documind.documents.answer_model.ChatOpenAI") as factory:
        with pytest.raises(ValueError):
            create_answer_model(settings, http_client=MagicMock(), http_async_client=MagicMock())
    factory.assert_not_called()


def test_factory_uses_configured_limits_and_shared_clients() -> None:
    settings = Settings(
        answer_model="  test-model  ",
        openai_api_key=SecretStr("test-key"),
        answer_request_timeout_seconds=12,
        answer_max_output_tokens=450,
    )
    http_client, http_async_client = MagicMock(), MagicMock()
    with patch("documind.documents.answer_model.ChatOpenAI") as factory:
        model = create_answer_model(
            settings, http_client=http_client, http_async_client=http_async_client
        )
    assert model is factory.return_value
    factory.assert_called_once_with(
        model="test-model",
        api_key=settings.openai_api_key,
        timeout=12,
        max_completion_tokens=450,
        max_retries=0,
        use_responses_api=True,
        store=False,
        http_client=http_client,
        http_async_client=http_async_client,
    )


@pytest.mark.parametrize(
    "configuration",
    [
        {"answer_model": ""},
        {"answer_request_timeout_seconds": 0},
        {"answer_request_timeout_seconds": -1},
        {"answer_max_output_tokens": 0},
        {"answer_max_output_tokens": -1},
    ],
)
def test_rejects_invalid_settings(configuration: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(configuration)


def test_reads_answer_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMIND_ANSWER_MODEL", "test-model")
    monkeypatch.setenv("DOCUMIND_ANSWER_REQUEST_TIMEOUT_SECONDS", "17.5")
    monkeypatch.setenv("DOCUMIND_ANSWER_MAX_OUTPUT_TOKENS", "600")
    settings = Settings(_env_file=None)
    assert settings.answer_model == "test-model"
    assert settings.answer_request_timeout_seconds == 17.5
    assert settings.answer_max_output_tokens == 600


@pytest.mark.parametrize("startup_fails", [False, True])
def test_answer_lifecycle_shares_and_closes_http_clients(
    s3_client_factory: MagicMock, startup_fails: bool
) -> None:
    settings = Settings(openai_api_key=SecretStr("test-key"), answer_model="test-model")
    application = create_app(settings)
    engine = AsyncMock(spec=AsyncEngine)
    model = MagicMock(spec=ChatOpenAI)

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            request = Request({"type": "http", "app": application})
            assert await get_answer_model(request) is model
            assert not answer_factory.call_args.kwargs["http_client"].is_closed
            assert not answer_factory.call_args.kwargs["http_async_client"].is_closed
            engine.dispose.assert_not_awaited()

    with (
        patch("documind.main.create_database_engine", return_value=engine),
        patch("documind.main.create_embeddings") as embedding_factory,
        patch("documind.main.create_answer_model", return_value=model) as answer_factory,
    ):
        if startup_fails:
            answer_factory.side_effect = ValueError("Invalid answer configuration")
            with pytest.raises(ValueError, match="Invalid answer configuration"):
                asyncio.run(run_lifespan())
        else:
            asyncio.run(run_lifespan())

        answer_factory.assert_called_once()
        assert answer_factory.call_args.args == (settings,)
        for name in ["http_client", "http_async_client"]:
            client = answer_factory.call_args.kwargs[name]
            assert client is embedding_factory.call_args.kwargs[name]
            assert client.is_closed
        engine.dispose.assert_awaited_once_with()
        s3_client_factory.return_value.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("api_key", "model_name"),
    [(None, None), (None, "test-model"), ("test-key", None)],
)
def test_missing_configuration_allows_startup_but_disables_answers(
    s3_client_factory: MagicMock, api_key: str | None, model_name: str | None
) -> None:
    settings = Settings(
        openai_api_key=SecretStr(api_key) if api_key is not None else None,
        answer_model=model_name,
    )
    application = create_app(settings)
    engine = AsyncMock(spec=AsyncEngine)

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            request = Request({"type": "http", "app": application})
            with pytest.raises(HTTPException) as captured:
                await get_answer_model(request)
            assert captured.value.status_code == 503
            assert captured.value.detail == "Document answer generation is unavailable"
            if api_key is not None:
                assert application.state.embeddings is embedding_factory.return_value

    with (
        patch("documind.main.create_database_engine", return_value=engine),
        patch("documind.main.create_embeddings") as embedding_factory,
        patch("documind.main.create_answer_model") as answer_factory,
    ):
        asyncio.run(run_lifespan())
    answer_factory.assert_not_called()
    engine.dispose.assert_awaited_once()


def test_real_factory_accepts_lifecycle_http_clients() -> None:
    async def create_model() -> None:
        with httpx.Client() as http_client:
            async with httpx.AsyncClient() as http_async_client:
                model = create_answer_model(
                    Settings(answer_model="test-model", openai_api_key=SecretStr("test-key")),
                    http_client=http_client,
                    http_async_client=http_async_client,
                )
                assert isinstance(model, ChatOpenAI)
                assert model.http_client is http_client
                assert model.http_async_client is http_async_client

    asyncio.run(create_model())
