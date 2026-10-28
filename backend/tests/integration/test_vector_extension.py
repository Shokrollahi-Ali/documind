import pytest
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration


def test_vector_extension_is_enabled(integration_database_engine: Engine) -> None:
    with integration_database_engine.connect() as connection:
        installed_version = connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )

    assert installed_version is not None
