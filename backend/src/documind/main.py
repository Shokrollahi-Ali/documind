from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, closing

import httpx
from fastapi import FastAPI

from documind.api.request_size import MULTIPART_OVERHEAD_BYTES, MaxBodySizeMiddleware
from documind.api.router import api_router
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.embeddings import create_embeddings
from documind.storage.s3 import create_s3_client


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        engine = create_database_engine(config)

        try:
            application.state.session_factory = create_session_factory(engine)
            application.state.embeddings = None
            with closing(create_s3_client(config)) as s3_client:
                application.state.s3_client = s3_client
                with httpx.Client() as http_client:
                    async with httpx.AsyncClient() as http_async_client:
                        if config.openai_api_key is not None:
                            application.state.embeddings = create_embeddings(
                                config,
                                http_client=http_client,
                                http_async_client=http_async_client,
                            )
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
    app.state.settings = config
    app.include_router(api_router)
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_body_size=config.max_upload_size_bytes + MULTIPART_OVERHEAD_BYTES,
    )
    return app


app = create_app()
