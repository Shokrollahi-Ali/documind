from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from documind.api.router import api_router
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        engine = create_database_engine(config)
        application.state.session_factory = create_session_factory(engine)

        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="Documind API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.environment != "production" else None,
    )
    app.include_router(api_router)
    return app


app = create_app()
