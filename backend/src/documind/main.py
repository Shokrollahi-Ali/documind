from fastapi import FastAPI

from documind.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Documind API")
    app.include_router(api_router)
    return app


app = create_app()
