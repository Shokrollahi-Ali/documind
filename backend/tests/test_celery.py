from unittest.mock import patch

import pytest
from pydantic import SecretStr

from documind.core.celery import create_celery_app
from documind.core.config import Settings


@pytest.mark.parametrize("broker_url", [None, "", "   "])
def test_rejects_missing_or_empty_broker_url(broker_url: str | None) -> None:
    settings = Settings(
        _env_file=None,
        celery_broker_url=SecretStr(broker_url) if broker_url is not None else None,
    )

    with pytest.raises(ValueError, match="DOCUMIND_CELERY_BROKER_URL"):
        create_celery_app(settings)


@pytest.mark.parametrize(
    "broker_url",
    ["redis://localhost:6379/0", "  redis://localhost:6379/0  "],
)
def test_configures_application_without_connecting_to_broker(
    broker_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    settings = Settings(_env_file=None, celery_broker_url=SecretStr(broker_url))

    with patch("kombu.Connection.connect") as connect:
        application = create_celery_app(settings)

        try:
            assert application.main == "documind"
            assert application.conf.broker_url == "redis://localhost:6379/0"
            assert application.conf.task_serializer == "json"
            assert application.conf.accept_content == ["json"]
            assert application.conf.task_ignore_result is True
            assert str(application.timezone) == "UTC"
            assert application.conf.enable_utc is True
            connect.assert_not_called()
        finally:
            application.close()
