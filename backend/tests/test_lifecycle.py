from fastapi.testclient import TestClient

from documind.main import create_app


def test_create_database_session_factory() -> None:
    app = create_app()
    with TestClient(app):
        assert app.state.session_factory is not None
