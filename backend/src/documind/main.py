from fastapi import FastAPI

app = FastAPI(title="Documind API")


@app.get("/health")
async def get_health() -> dict[str, str]:
    return {"status": "ok"}
