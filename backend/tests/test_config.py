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


@pytest.mark.parametrize("session_lifetime_seconds", [0, -1])
def test_rejects_non_positive_session_lifetime(session_lifetime_seconds: int) -> None:
    with pytest.raises(ValidationError, match="session_lifetime_seconds"):
        Settings(
            _env_file=None,
            session_lifetime_seconds=session_lifetime_seconds,
        )


def test_reads_session_lifetime_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMIND_SESSION_LIFETIME_SECONDS", "3600")

    settings = Settings(_env_file=None)

    assert settings.session_lifetime_seconds == 3600


def test_reads_session_cookie_name_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMIND_SESSION_COOKIE_NAME", "custom_session")

    settings = Settings(_env_file=None)

    assert settings.session_cookie_name == "custom_session"


def test_rejects_empty_session_cookie_name() -> None:
    with pytest.raises(ValidationError, match="session_cookie_name"):
        Settings(_env_file=None, session_cookie_name="")
