from documind.core.config import Settings
from documind.main import create_app


def test_enables_documentation_in_development() -> None:
    app = create_app(Settings(environment="development"))

    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"


def test_disables_documentation_in_production() -> None:
    app = create_app(Settings(environment="production"))

    assert app.docs_url is None
    assert app.openapi_url is None
