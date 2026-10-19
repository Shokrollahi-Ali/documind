import pytest
from pydantic import ValidationError

from documind.core.config import Settings

PRODUCTION_DATABASE_URL = "postgresql+psycopg://documind:production-secret@db.internal/documind"


@pytest.fixture(autouse=True)
def clear_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCUMIND_DATABASE_URL", raising=False)


def test_rejects_default_database_url_in_production() -> None:
    with pytest.raises(ValidationError, match="DOCUMIND_DATABASE_URL must be set"):
        Settings(_env_file=None, environment="production")


def test_rejects_local_database_password_in_production() -> None:
    with pytest.raises(ValidationError, match="DOCUMIND_DATABASE_URL must be set"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://documind:documind-local-only@db.internal/documind",
        )


def test_accepts_explicit_database_url_in_production() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url=PRODUCTION_DATABASE_URL,
    )

    assert settings.database_url.get_secret_value() == PRODUCTION_DATABASE_URL


@pytest.mark.parametrize("environment", ["development", "test"])
def test_allows_default_database_url_outside_production(environment: str) -> None:
    settings = Settings(_env_file=None, environment=environment)

    assert "documind-local-only" in settings.database_url.get_secret_value()
