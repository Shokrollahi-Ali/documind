from fastapi import FastAPI

from documind.api.router import api_router
from documind.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    app = FastAPI(
        title="Documind API",
        version="0.1.0",
        docs_url="/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.environment != "production" else None,
    )
    app.include_router(api_router)
    return app


app = create_app()
